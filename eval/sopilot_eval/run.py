"""CLI: python -m sopilot_eval.run --dataset datasets/smoke --config configs/smoke.yaml

Writes results/<run_id>/{run.json, metrics.json, per_question.jsonl, report.md}.
Retrieval-only (no LLM), so it can be rerun freely (ADR-006 §4.2).

Two dataset layouts:

* legacy: ``questions.jsonl`` with ``expected`` doc/page targets (document/page proxy metrics);
* V2-06 (``questions.master.jsonl`` + ``evidence.jsonl`` + ``manifest.json``): pass ``--split``.
  The dataset validator runs first (frozen test hash, reviews), and answerable questions are also
  scored against the gold spans when chunks carry offsets (``chunking.mode: docproc``).
"""
from __future__ import annotations
from typing import Any

import argparse
import json
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import yaml

from .corpus import load_chunks
from .embedders import build_embedder
from .metrics import refusal_sweep, retrieval_metrics, span_metrics
from .retrievers import TOKENIZER_VERSION, CrossEncoder, Index, build_reranker, retrieve_candidates

ROOT = Path(__file__).resolve().parents[1]


def _git_state() -> dict:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    try:
        dirty = git("status", "--porcelain", "--", "sopilot_eval", "configs", "../services/ai-service/src")
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(dirty)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unknown", "dirty": None}


def _groups(q: dict) -> list[str]:
    """Report groups for one question: language, same/cross-lingual and each query type."""
    g = [f"lang={q['lang']}"] if q.get("lang") else []
    g.append("cross_lingual" if q.get("cross_lingual") else "same_lingual")
    if q.get("lang"):
        g.append(f"lang={q['lang']}&{'cross' if q.get('cross_lingual') else 'same'}")
    g.extend(f"query_type={kind}" for kind in q.get("query_types", []))
    if q.get("subset"):
        g.append(f"subset={q['subset']}")
    g.extend(f"tag={tag}" for tag in q.get("tags", []))
    return g


def _percentile(xs: list[float], p: float) -> float:
    return float(np.percentile(xs, p)) if xs else 0.0


def _peak_rss_mb() -> float | None:
    """Peak working set of this process (Windows) or max RSS (POSIX)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
            if not kernel32.K32GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return None
            return round(pmc.PeakWorkingSetSize / 2**20, 1)
        import resource

        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except (OSError, AttributeError, ImportError):
        return None


def load_questions(dataset: Path, split: str | None, allow_draft: bool = False) -> tuple[list[dict], dict, dict]:
    """Questions, gold spans by id, and dataset provenance.

    ``allow_draft`` skips the human-review gate for a *preview* run on unreviewed questions; the
    provenance then says ``reviewed: false`` and such numbers are not official results.
    """
    if (dataset / "questions.master.jsonl").is_file():
        from .dataset import read_jsonl, validate_retrieval

        if split not in ("dev", "test", "all"):
            raise ValueError("V2-06 datasets need --split dev|test|all")
        info = validate_retrieval(dataset, require_reviewed=not allow_draft)
        info["reviewed"] = not allow_draft
        questions = read_jsonl(dataset / "questions.master.jsonl")
        if split != "all":
            questions = [q for q in questions if q["split"] == split]
        spans = {s["span_id"]: s for s in read_jsonl(dataset / "evidence.jsonl")}
        return questions, spans, {"format": "v2-06", "split": split, **info}
    if split not in (None, "all"):
        raise ValueError("--split only applies to V2-06 datasets (questions.master.jsonl)")
    questions = [
        json.loads(line)
        for line in (dataset / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return questions, {}, {"format": "legacy"}


def _chunks_for(dataset: Path, chunk_cfg: dict, embedder_cfg: dict):
    mode = chunk_cfg.get("mode", "character")
    if mode == "character":
        chunks = load_chunks(dataset / "corpus", chunk_cfg.get("size", 800), chunk_cfg.get("overlap", 100))
        return chunks, {"mode": "character_exploratory_only", "size": chunk_cfg.get("size", 800),
                        "overlap": chunk_cfg.get("overlap", 100)}
    if mode != "docproc":
        raise ValueError(f"unknown chunking mode: {mode}")
    tok = embedder_cfg.get("tokenizer") or (
        {"model": embedder_cfg["model"], "revision": embedder_cfg.get("revision")}
        if embedder_cfg.get("provider") == "sentence-transformers" else None
    )
    if not (dataset / "manifest.json").is_file() or tok is None:
        raise ValueError("docproc chunking needs a docproc dataset (manifest.json) and the model "
                         "tokenizer; no silent fallback to character chunks")
    from .docproc_chunks import load_docproc_chunks

    def resolve(key: str) -> Path | None:
        value = chunk_cfg.get(key)
        return (ROOT / value) if value else None

    return load_docproc_chunks(
        dataset, tok["model"], tok.get("revision"), resolve("structured_dir"), resolve("pilot_dataset"),
        chunk_cfg.get("target_tokens", 384), chunk_cfg.get("max_tokens", 512),
    )


def _chunk_key(c) -> str:
    if c.char_start is not None:
        return f"{c.doc_id}:{c.char_start}-{c.char_end}"
    return f"{c.doc}:p{c.page}:{c.sha[:12]}"


def run(dataset: Path, config_path: Path, out_root: Path, split: str | None = None, repeats: int = 1,
        allow_draft: bool = False) -> Path:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    names = [conf["name"] for conf in cfg["configs"]]
    if not names or len(set(names)) != len(names):
        raise ValueError("evaluation configuration names must be nonempty and unique")
    if any("api_key" in conf["embedder"] for conf in cfg["configs"]):
        raise ValueError("use api_key_env, never store credentials in run config")
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    questions, spans, data_info = load_questions(dataset, split, allow_draft)
    chunk_cfg = cfg.get("chunking", {})
    if not questions:
        raise ValueError("evaluation requires a nonempty question set")

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    out = out_root / run_id
    out.mkdir(parents=True, exist_ok=True)

    metrics: dict[str, dict] = {}
    per_q: list[dict] = []
    indexes: dict[str, tuple[Index, dict]] = {}
    rerankers: dict[str, Any] = {}
    chunking_info: dict[str, dict] = {}

    for conf in cfg["configs"]:
        emb_key = json.dumps(conf["embedder"], sort_keys=True)
        if emb_key not in indexes:
            chunks, cinfo = _chunks_for(dataset, chunk_cfg, conf["embedder"])
            if not chunks:
                raise ValueError("evaluation requires a nonempty corpus")
            t0 = time.perf_counter()
            embedder = build_embedder(conf["embedder"], ROOT / ".cache")
            t1 = time.perf_counter()
            index = Index(chunks, embedder)
            t2 = time.perf_counter()
            indexes[emb_key] = (index, {"model_load_s": round(t1 - t0, 2), "corpus_embed_s": round(t2 - t1, 2),
                                        "n_chunks": len(chunks)})
            chunking_info[emb_key] = cinfo
        index, emb_info = indexes[emb_key]
        reranker = None
        if conf.get("rerank"):
            rk = json.dumps(conf["rerank"], sort_keys=True)
            if rk not in rerankers:
                rc = conf["rerank"]
                rerankers[rk] = (build_reranker(rc) if rc.get("provider", "local") != "local"
                                 else CrossEncoder(rc["model"], rc.get("revision")))
            reranker = rerankers[rk]
        k_prompt = conf.get("k", 5)
        if not isinstance(k_prompt, int) or k_prompt <= 0:
            raise ValueError("k must be a positive integer")
        ks = tuple(sorted({1, 3, 5, 10, k_prompt}))
        pool = max(25, k_prompt)

        agg: dict[str, list[float]] = {}
        groups: dict[str, dict[str, list[float]]] = {}
        run_p50: list[float] = []
        run_p95: list[float] = []
        first_ranks: dict[str, list[str]] = {}
        rank_stable = True
        ans_scores: list[float] = []
        unans_scores: list[float] = []
        gated = True
        for rep in range(repeats):
            latencies: list[float] = []
            for q in questions:
                t0 = time.perf_counter()
                cands = retrieve_candidates(index, q["question"], conf, reranker, pool=pool, query_lang=q.get("lang"))
                latencies.append((time.perf_counter() - t0) * 1000)
                ranked_keys = [_chunk_key(index.chunks[c["idx"]]) for c in cands]
                if rep:
                    rank_stable &= first_ranks[q["id"]] == ranked_keys
                    continue
                first_ranks[q["id"]] = ranked_keys
                top = cands[0]["gate"] if cands else None
                gated &= top is not None
                row = {"config": conf["name"], "id": q["id"], "split": q.get("split"), "lang": q.get("lang"),
                       "cross_lingual": bool(q.get("cross_lingual")), "query_types": q.get("query_types", []),
                       "intent_id": q.get("intent_id"), "subset": q.get("subset"), "tags": q.get("tags", []),
                       "answerable": bool(q["answerable"]), "gate_score": top, "ranked": ranked_keys,
                       "top5": [{k: v for k, v in c.items() if k != "idx"} for c in cands[:5]]}
                if q["answerable"]:
                    ranked_chunks = [index.chunks[c["idx"]] for c in cands]
                    m = retrieval_metrics(ranked_chunks, q["expected"], ks=ks)
                    if spans and ranked_chunks and ranked_chunks[0].char_start is not None:
                        m.update(span_metrics(ranked_chunks, q["evidence_sets"], spans, ks=ks))
                    for k, v in m.items():
                        agg.setdefault(k, []).append(v)
                        for g in _groups(q):
                            groups.setdefault(g, {}).setdefault(k, []).append(v)
                    if top is not None:
                        ans_scores.append(top)
                    row.update(m)
                elif top is not None:
                    unans_scores.append(top)
                per_q.append(row)
            run_p50.append(_percentile(latencies, 50))
            run_p95.append(_percentile(latencies, 95))

        metrics[conf["name"]] = {
            "n_answerable": sum(bool(q["answerable"]) for q in questions),
            "n_unanswerable": sum(not q["answerable"] for q in questions),
            **{k: round(float(np.mean(v)), 4) for k, v in agg.items()},
            "by_group": {
                g: {"n": len(next(iter(d.values()))), **{k: round(float(np.mean(v)), 4) for k, v in d.items()}}
                for g, d in sorted(groups.items())
            },
            "latency_ms_p50": round(float(np.mean(run_p50)), 2),
            "latency_ms_p50_sd": round(float(np.std(run_p50)), 2),
            "latency_ms_p95": round(float(np.mean(run_p95)), 2),
            "latency_ms_p95_sd": round(float(np.std(run_p95)), 2),
            "latency_runs": repeats,
            "rank_stable_across_runs": rank_stable if repeats > 1 else None,
            **emb_info,
            "gate": ("none (bm25 has no gate)" if not gated else
                     "rerank_score (sigmoid)" if conf.get("rerank") else "dense_score (cosine)"),
            "refusal_sweep": refusal_sweep(ans_scores, unans_scores) if gated else [],
        }

    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "per_question.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in per_q), encoding="utf-8")
    chunk_infos = list(chunking_info.values())
    (out / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "git": _git_state(),
                "dataset": str(dataset),
                "dataset_info": data_info,
                "n_questions": len(questions),
                "metric_scope": "span_gold+document_page_proxy" if spans and chunk_infos[0]["mode"] == "docproc"
                else "document_page_proxy",
                "chunking_mode": chunk_infos[0]["mode"],
                "chunking": chunk_infos,
                "bm25_tokenizer": TOKENIZER_VERSION,
                "config": cfg,
                "repeats": repeats,
                "peak_rss_mb": _peak_rss_mb(),
                "python": platform.python_version(),
                "machine": platform.platform(),
                "processor": platform.processor(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_report(run_id, dataset, chunk_infos[0]["mode"], metrics), encoding="utf-8")
    return out


def render_report(run_id: str, dataset: Path, chunking_mode: str, metrics: dict) -> str:
    span = any("span_recall@5" in m for m in metrics.values())
    cols = (["span_recall@5", "full@5", "any@5", "mrr_span", "hit@5", "recall@10"] if span
            else ["recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@10"])
    cols += ["latency_ms_p50", "latency_ms_p95"]
    lines = [
        f"# Eval run {run_id}",
        "",
        f"Dataset: `{dataset}`. Chunking: `{chunking_mode}`. Retrieval-only; no LLM.",
        "",
        "| config | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for name, m in metrics.items():
        lines.append(f"| {name} | " + " | ".join(str(m.get(c, "")) for c in cols) + " |")
    lines += ["", "## By group (answerable questions only)", ""]
    gcols = ["n"] + (["span_recall@5", "full@5", "any@5", "mrr_span"] if span else ["recall@1", "recall@5", "mrr", "ndcg@10"])
    lines += ["| config | group | " + " | ".join(gcols) + " |", "|---|---|" + "---|" * len(gcols)]
    for name, m in metrics.items():
        for g, d in m["by_group"].items():
            lines.append(f"| {name} | {g} | " + " | ".join(str(d.get(c, "")) for c in gcols) + " |")
    lines += ["", "## Refusal threshold sweep (RQ3, top-1 gate score)", ""]
    for name, m in metrics.items():
        lines += [f"### {name} (gate: {m['gate']})", ""]
        if not m["refusal_sweep"]:
            lines += ["No gate for this mode.", ""]
            continue
        lines += ["| threshold | false_refusal | false_answer |", "|---|---|---|"]
        lines += [f"| {r['threshold']:.4f} | {r['false_refusal']} | {r['false_answer']} |" for r in m["refusal_sweep"]]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    ap.add_argument("--split", choices=["dev", "test", "all"])
    ap.add_argument("--repeats", type=int, default=1, help="query passes for latency (ranks checked equal)")
    ap.add_argument("--allow-draft", action="store_true",
                    help="preview run on unreviewed questions (run.json dataset_info.reviewed=false; not official)")
    a = ap.parse_args()
    sys.stdout.write(str(run(a.dataset, a.config, a.out, a.split, a.repeats, a.allow_draft)) + "\n")


if __name__ == "__main__":
    main()
