"""CLI: python -m sopilot_eval.run --dataset datasets/smoke --config configs/smoke.yaml

Writes results/<run_id>/{run.json, metrics.json, per_question.jsonl, report.md}.
Retrieval-only (no LLM), so it can be rerun freely (ADR-006 §4.2).
"""
from __future__ import annotations

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
from .metrics import refusal_sweep, retrieval_metrics
from .retrievers import CrossEncoder, Index, retrieve

ROOT = Path(__file__).resolve().parents[1]


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _groups(q: dict) -> list[str]:
    """Report groups for one question: its language, and cross-lingual when flagged."""
    g = [f"lang={q['lang']}"] if q.get("lang") else []
    if q.get("cross_lingual"):
        g.append("cross_lingual")
    g.extend(f"query_type={kind}" for kind in q.get("query_types", []))
    return g


def _percentile(xs: list[float], p: float) -> float:
    return float(np.percentile(xs, p)) if xs else 0.0


def run(dataset: Path, config_path: Path, out_root: Path) -> Path:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    names = [conf["name"] for conf in cfg["configs"]]
    if not names or len(set(names)) != len(names):
        raise ValueError("evaluation configuration names must be nonempty and unique")
    if any("api_key" in conf["embedder"] for conf in cfg["configs"]):
        raise ValueError("use api_key_env, never store credentials in run config")
    questions = [json.loads(l) for l in (dataset / "questions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    chunk_cfg = cfg.get("chunking", {})
    if chunk_cfg.get("mode", "character") != "character":
        raise ValueError("docproc chunking is not implemented yet (V2-22/V2-07); no silent fallback")
    chunks = load_chunks(dataset / "corpus", chunk_cfg.get("size", 800), chunk_cfg.get("overlap", 100))
    if not chunks or not questions:
        raise ValueError("evaluation requires a nonempty corpus and question set")

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    out = out_root / run_id
    out.mkdir(parents=True, exist_ok=True)

    metrics: dict[str, dict] = {}
    per_q: list[dict] = []
    indexes: dict[str, tuple[Index, float]] = {}
    rerankers: dict[str, CrossEncoder] = {}

    for conf in cfg["configs"]:
        emb_key = json.dumps(conf["embedder"], sort_keys=True)
        if emb_key not in indexes:
            t0 = time.perf_counter()
            embedder = build_embedder(conf["embedder"], ROOT / ".cache")
            indexes[emb_key] = (Index(chunks, embedder), time.perf_counter() - t0)
        index, embed_s = indexes[emb_key]
        reranker = None
        if conf.get("rerank"):
            rk = json.dumps(conf["rerank"], sort_keys=True)
            if rk not in rerankers:
                rerankers[rk] = CrossEncoder(conf["rerank"]["model"], conf["rerank"].get("revision"))
            reranker = rerankers[rk]
        k_prompt = conf.get("k", 5)
        if not isinstance(k_prompt, int) or k_prompt <= 0:
            raise ValueError("k must be a positive integer")

        agg: dict[str, list[float]] = {}
        groups: dict[str, dict[str, list[float]]] = {}
        latencies: list[float] = []
        ans_scores: list[float] = []
        unans_scores: list[float] = []
        for q in questions:
            t0 = time.perf_counter()
            ranked = retrieve(index, q["question"], conf, reranker, pool=max(25, k_prompt))
            latencies.append((time.perf_counter() - t0) * 1000)
            top = ranked[0][1] if ranked else 0.0
            if q["answerable"]:
                ans_scores.append(top)
                m = retrieval_metrics([index.chunks[i] for i, _ in ranked], q["expected"], ks=(1, 3, 5, 10, k_prompt))
                for k, v in m.items():
                    agg.setdefault(k, []).append(v)
                    for g in _groups(q):
                        groups.setdefault(g, {}).setdefault(k, []).append(v)
                per_q.append({"config": conf["name"], "id": q["id"], "top_score": top, **m})
            else:
                unans_scores.append(top)
                per_q.append({"config": conf["name"], "id": q["id"], "top_score": top, "answerable": False})

        metrics[conf["name"]] = {
            "n_answerable": len(ans_scores),
            "n_unanswerable": len(unans_scores),
            **{k: round(float(np.mean(v)), 4) for k, v in agg.items()},
            "by_group": {
                g: {"n": len(next(iter(d.values()))), **{k: round(float(np.mean(v)), 4) for k, v in d.items()}}
                for g, d in sorted(groups.items())
            },
            "latency_ms_p50": round(_percentile(latencies, 50), 2),
            "latency_ms_p95": round(_percentile(latencies, 95), 2),
            "corpus_embed_s": round(embed_s, 2),
            "refusal_sweep": refusal_sweep(ans_scores, unans_scores),
        }

    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "per_question.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in per_q), encoding="utf-8")
    (out / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "git_commit": _git_commit(),
                "dataset": str(dataset),
                "n_chunks": len(chunks),
                "n_questions": len(questions),
                "metric_scope": "document_page_proxy",
                "chunking_mode": "character_exploratory_only",
                "config": cfg,
                "python": platform.python_version(),
                "machine": platform.platform(),
                "processor": platform.processor(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_report(run_id, dataset, len(chunks), metrics), encoding="utf-8")
    return out


def render_report(run_id: str, dataset: Path, n_chunks: int, metrics: dict) -> str:
    cols = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@10", "latency_ms_p50", "latency_ms_p95"]
    lines = [
        f"# Eval run {run_id}",
        "",
        f"Dataset: `{dataset}` ({n_chunks} chunks). Retrieval-only; no LLM.",
        "Metrics are document/page proxies with character chunks; not span-gold research results (V2-07/V2-22).",
        "",
        "| config | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for name, m in metrics.items():
        lines.append(f"| {name} | " + " | ".join(str(m.get(c, "")) for c in cols) + " |")
    lines += ["", "## By language / cross-lingual (answerable questions only)", ""]
    gcols = ["n", "recall@1", "recall@5", "mrr", "ndcg@10"]
    lines += ["| config | group | " + " | ".join(gcols) + " |", "|---|---|" + "---|" * len(gcols)]
    for name, m in metrics.items():
        for g, d in m["by_group"].items():
            lines.append(f"| {name} | {g} | " + " | ".join(str(d.get(c, "")) for c in gcols) + " |")
    lines += ["", "## Refusal threshold sweep (RQ3, top-1 score gate)", ""]
    for name, m in metrics.items():
        lines += [f"### {name}", "", "| threshold | false_refusal | false_answer |", "|---|---|---|"]
        lines += [f"| {r['threshold']} | {r['false_refusal']} | {r['false_answer']} |" for r in m["refusal_sweep"]]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    a = ap.parse_args()
    sys.stdout.write(str(run(a.dataset, a.config, a.out)) + "\n")


if __name__ == "__main__":
    main()
