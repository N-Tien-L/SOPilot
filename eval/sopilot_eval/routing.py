"""Routing evaluation (V2-27): (a) rules only vs (b) rules + semantic router.

The harness calls the production code and copies none of it: the rules run through
``sopilot_ai.qa.steps.deterministic_steps`` (input, PII, frame, guard, router, meaningful tokens),
the semantic layer is ``sopilot_ai.qa.router.SemanticLayer`` built with the service's own
``LocalEmbeddingProvider``. Config (a) needs no model.

Per label the harness reports precision and recall, the costly and cheap error classes of the
ticket, the off-topic -> gap-list rate, and latency p50/p95 of the router step. Acceptance uses the
thresholds written in the config (ticket V2-27: sop_question routed away <= 2 %, and no more costly
errors than config (a)).

Run from ``eval/`` or from the repository root; dataset, exemplar and threshold paths in the config
are repository-relative and resolved against the repository root (not the working directory).

    uv run python -m sopilot_eval.routing --config configs/routing-rules-router.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sopilot_ai.qa import router
from sopilot_ai.qa.pipeline import DecisionKind, PipelineContext, run_steps
from sopilot_ai.qa.steps import deterministic_steps

EVAL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EVAL_ROOT.parent

LABELS = (
    "greeting", "thanks", "about_bot", "abuse_only", "abuse_with_question", "harmful", "followup",
    "sop_question", "off_topic", "action_request", "personal_data", "legal_medical", "about_source",
    "feedback_in_chat",
)
TEMPLATE_LABELS = {"greeting", "thanks", "about_bot", "abuse_only"}
RAG = "rag"  # the question goes to retrieval as before
# What a row of each label must be predicted as. followup is only measured (TECH §7.1 step 4).
EXPECTED = {label: label for label in LABELS}
EXPECTED.update({"sop_question": RAG, "followup": RAG, "off_topic": router.OUT_OF_SCOPE_CANDIDATE})
COSTLY_SOURCES = {"sop_question", "followup"}  # a business or follow-up question routed away
CHEAP_SOURCES = {"greeting", "thanks", "about_bot", "abuse_only", "abuse_with_question"}
# Ticket V2-27 acceptance defaults; a config may override them under `acceptance`.
DEFAULT_ACCEPTANCE = {"sop_misroute_max": 0.02}


def resolve_path(value: str) -> Path:
    """Repository-relative paths first, then the working directory; absolute paths as given."""
    path = Path(value)
    if path.is_absolute():
        return path
    for base in (REPO_ROOT, Path.cwd()):
        candidate = base / path
        if candidate.exists():
            return candidate.resolve()
    return (REPO_ROOT / path).resolve()


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@dataclass(frozen=True)
class Prediction:
    label: str  # what the route is: a label of LABELS, RAG, or another template key
    layer: str  # "rule" | "semantic" | "none"
    router_ms: float | None  # semantic step latency (embed + decide); None when it did not run


def load_vocabulary(corpus_dir: Path) -> frozenset[str]:
    """Words of the asker's documents (raw and diacritic-free). ai-service reads the same set from
    rag.chunk_terms through the access filter; the harness reads the eval corpus instead."""
    from sopilot_ai.qa.textnorm import tokenize_words

    vocab: set[str] = set()
    for path in sorted(corpus_dir.glob("*.md")) + sorted(corpus_dir.glob("*.txt")):
        for tok in tokenize_words(path.read_text(encoding="utf-8")):
            vocab.add(tok.raw)
            vocab.add(tok.folded)
    return frozenset(vocab)


async def _rules(text: str, vocab: frozenset[str]) -> tuple[str, PipelineContext]:
    async def known_terms(words: Sequence[str]) -> set[str]:
        return {w for w in words if w in vocab}

    ctx = PipelineContext(question=text, known_terms=known_terms)
    decision = await run_steps(deterministic_steps(), ctx)
    if decision.kind is DecisionKind.REFUSE:
        return ("harmful" if decision.outcome == "REFUSED_GUARD" else decision.outcome or "refused"), ctx
    if decision.kind is DecisionKind.TEMPLATE:
        key = decision.template_key or ""
        return (key if key in TEMPLATE_LABELS else "not_understood"), ctx
    if ctx.stripped is not None and "abuse" in ctx.stripped.kinds:
        return "abuse_with_question", ctx
    return RAG, ctx


def predict_rules(texts: Sequence[str], vocab: frozenset[str]) -> list[tuple[str, PipelineContext]]:
    async def run_all() -> list[tuple[str, PipelineContext]]:
        return [await _rules(t, vocab) for t in texts]

    return asyncio.run(run_all())


def predict(rows: Sequence[dict[str, Any]], layer: router.SemanticLayer | None,
            vocab: frozenset[str]) -> list[Prediction]:
    """Config (a) when ``layer`` is None, config (b) otherwise (the router step only where the
    rules left the question to RAG, as in the service)."""
    rules = predict_rules([r["text"] for r in rows], vocab)
    out: list[Prediction] = []
    for row, (label, ctx) in zip(rows, rules, strict=True):
        if layer is None or label not in (RAG, "abuse_with_question"):
            out.append(Prediction(label, "rule", None))
            continue
        started = time.perf_counter()
        decision = layer.classify(ctx.text, has_history=row.get("previous_turn") is not None)
        elapsed = (time.perf_counter() - started) * 1000
        if decision.intent is None or router.action_for(decision.intent) == router.ACTION_RAG:
            out.append(Prediction(label, "semantic", elapsed))  # no route: the rule decision stands
        else:
            out.append(Prediction(decision.intent, "semantic", elapsed))
    return out


def _safe_div(num: float, den: float) -> float | None:
    return num / den if den else None


def per_label(rows: Sequence[dict[str, Any]], preds: Sequence[Prediction]) -> dict[str, dict]:
    """Precision and recall per label. A label's "hit" is its expected route (EXPECTED)."""
    out: dict[str, dict] = {}
    for label in LABELS:
        want = EXPECTED[label]
        true_n = sum(r["intent"] == label for r in rows)
        hit = sum(r["intent"] == label and p.label == want for r, p in zip(rows, preds, strict=True))
        pred_n = sum(p.label == want for p in preds)
        pred_true = sum(p.label == want and EXPECTED[r["intent"]] == want
                        for r, p in zip(rows, preds, strict=True))
        out[label] = {
            "n": true_n, "expected_route": want,
            "recall": _safe_div(hit, true_n), "precision": _safe_div(pred_true, pred_n),
            "predicted": pred_n,
        }
    return out


def error_classes(rows: Sequence[dict[str, Any]], preds: Sequence[Prediction]) -> dict[str, Any]:
    """Costly = a business or follow-up question routed away from RAG. Cheap = a greeting, thanks,
    about-bot or profanity question that reached RAG (answered "not found" instead of a sentence),
    or a profanity question with content that the rules did not see as profanity."""
    costly = cheap = other = 0
    for r, p in zip(rows, preds, strict=True):
        intent = r["intent"]
        if intent in COSTLY_SOURCES and p.label != RAG:
            costly += 1
        elif intent in CHEAP_SOURCES and p.label == RAG:
            cheap += 1
        elif EXPECTED[intent] != p.label and intent not in ("harmful",):
            other += 1
    return {"costly": costly, "cheap": cheap, "other_misses": other}


def summarize(rows: Sequence[dict[str, Any]], preds: Sequence[Prediction],
              acceptance: dict[str, float] | None = None,
              baseline_costly: int | None = None) -> dict[str, Any]:
    acc = {**DEFAULT_ACCEPTANCE, **(acceptance or {})}
    sop = [p for r, p in zip(rows, preds, strict=True) if r["intent"] == "sop_question"]
    sop_routed = sum(p.label != RAG for p in sop)
    sop_rate = _safe_div(sop_routed, len(sop)) or 0.0
    off = [p for r, p in zip(rows, preds, strict=True) if r["intent"] == "off_topic"]
    off_gap = sum(p.label != router.OUT_OF_SCOPE_CANDIDATE for p in off)
    followups = [p for r, p in zip(rows, preds, strict=True) if r["intent"] == "followup"]
    errors = error_classes(rows, preds)
    latencies = [p.router_ms for p in preds if p.router_ms is not None]
    result: dict[str, Any] = {
        "total": len(rows),
        "per_label": per_label(rows, preds),
        "errors": errors,
        "sop_question": {"n": len(sop), "routed_away": sop_routed, "rate": sop_rate},
        "sop_candidate_out_of_scope": sum(p.label == router.OUT_OF_SCOPE_CANDIDATE for p in sop),
        "off_topic": {"n": len(off), "to_gap_list_upper_bound": off_gap,
                      "rate": _safe_div(off_gap, len(off))},
        "followup": {"n": len(followups),
                     "routed_away": sum(p.label != RAG for p in followups),
                     "note": "retrieval and refusal of followup need qa/pipeline.py and a corpus; not measured here"},
        "router_latency_ms": {
            "ran_on": len(latencies),
            "p50": _percentile(latencies, 50), "p95": _percentile(latencies, 95),
        },
    }
    checks = {"sop_misroute_ok": sop_rate <= acc["sop_misroute_max"]}
    if baseline_costly is not None:
        checks["costly_not_above_baseline"] = errors["costly"] <= baseline_costly
    result["acceptance"] = {"thresholds": acc, "checks": checks,
                            "passed": all(checks.values())}
    return result


def _percentile(values: Iterable[float], pct: int) -> float | None:
    data = sorted(values)
    if not data:
        return None
    if len(data) == 1:
        return data[0]
    return statistics.quantiles(data, n=100, method="inclusive")[pct - 1]


def build_layer(cfg: dict[str, Any]) -> router.SemanticLayer | None:
    """The layer exactly as the service builds it: flag, embedder and files from the config."""
    if not cfg.get("semantic_router_enabled", False):
        return None  # config (a): no model is loaded
    from sopilot_ai.providers.embedding import LocalEmbeddingProvider
    from sopilot_ai.providers.registry import ModelsConfig

    emb_cfg = cfg["embedder"]
    spec = ModelsConfig.load(resolve_path(emb_cfg["models_config"])).embedding()
    revision = str(emb_cfg["revision"])

    def factory() -> router.QueryEmbedder:
        return LocalEmbeddingProvider(spec, revision)

    return router.build_semantic_layer(
        enabled=bool(cfg.get("semantic_router_enabled", False)),
        embedder_factory=factory,
        model_id=f"{spec.model}@{revision}",
        exemplars=router.load_exemplars(resolve_path(cfg["exemplars"])),
        thresholds=router.load_thresholds(resolve_path(cfg["thresholds"])),
    )


def _write_report(out_dir: Path, filename: str, name: str, split: str, results: dict[str, Any],
                  model_info: dict[str, Any]) -> None:
    lines = [f"# Routing evaluation: {name} ({split})", "",
             f"- model: {json.dumps(model_info, ensure_ascii=False)}",
             f"- total rows: {results['total']}", "", "## Per label", "",
             "| label | n | expected route | recall | precision | predicted |", "|---|---|---|---|---|---|"]
    for label, m in results["per_label"].items():
        lines.append(f"| {label} | {m['n']} | {m['expected_route']} | {_fmt(m['recall'])} | "
                     f"{_fmt(m['precision'])} | {m['predicted']} |")
    lines += ["", "## Error classes and gap list", "",
              f"- costly (sop_question / followup routed away): {results['errors']['costly']}",
              f"- cheap (greeting/thanks/about_bot/profanity reached RAG): {results['errors']['cheap']}",
              f"- other misses: {results['errors']['other_misses']}",
              (f"- sop_question routed away: {results['sop_question']['routed_away']} of "
              f"{results['sop_question']['n']} ({_fmt(results['sop_question']['rate'])})"),
              (f"- off_topic to gap list (upper bound, gate assumed to refuse): "
              f"{_fmt(results['off_topic']['rate'])}"),
              f"- followup routed away: {results['followup']['routed_away']} of {results['followup']['n']}",
              (f"- router latency ms: p50 {_fmt(results['router_latency_ms']['p50'])}, "
              f"p95 {_fmt(results['router_latency_ms']['p95'])} "
              f"(on {results['router_latency_ms']['ran_on']} rows)"), "",
              "## Acceptance", "", f"- thresholds: {json.dumps(results['acceptance']['thresholds'])}",
              f"- checks: {json.dumps(results['acceptance']['checks'])}",
              f"- passed: {results['acceptance']['passed']}", ""]
    (out_dir / filename).write_text("\n".join(lines), encoding="utf-8")


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def run(config_path: Path, split: str | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    split = split or cfg.get("split", "test")
    rows = load_dataset(resolve_path(cfg["datasets"][split]))
    vocab = load_vocabulary(resolve_path(cfg["vocabulary"]))
    name = cfg["name"]
    out_dir = EVAL_ROOT / "results" / "routing" / f"{name}-{split}"
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline = None
    baseline_costly = None
    if cfg.get("baseline"):
        base_cfg = yaml.safe_load(resolve_path(cfg["baseline"]).read_text(encoding="utf-8"))
        base_preds = predict(rows, None, vocab)
        baseline = summarize(rows, base_preds, base_cfg.get("acceptance"))
        baseline_costly = baseline["errors"]["costly"]
        _write_report(out_dir, "baseline_report.md", base_cfg["name"], split, baseline,
                      {"semantic_router": False})
        (out_dir / "baseline_metrics.json").write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")

    layer = build_layer(cfg)
    model_info: dict[str, Any] = {"semantic_router": layer is not None}
    if layer is not None:
        layer.embed_query("khởi động")  # warm the model before timing
        model_info["model_id"] = layer.model_id
        model_info["thresholds"] = cfg["thresholds"]
    preds = predict(rows, layer, vocab)
    results = summarize(rows, preds, cfg.get("acceptance"), baseline_costly)
    results["baseline"] = baseline
    (out_dir / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    with (out_dir / "per_question.jsonl").open("w", encoding="utf-8") as fh:
        for r, p in zip(rows, preds, strict=True):
            fh.write(json.dumps({"id": r["id"], "intent": r["intent"], "pred": p.label,
                                 "layer": p.layer, "router_ms": p.router_ms},
                                ensure_ascii=False) + "\n")
    _write_report(out_dir, "report.md", name, split, results, model_info)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Routing evaluation (V2-27)")
    parser.add_argument("--config", required=True, help="config yaml (repository-relative paths)")
    parser.add_argument("--split", choices=("dev", "test"), default=None)
    args = parser.parse_args()
    results = run(resolve_path(args.config), args.split)
    summary = {k: results[k] for k in ("total", "sop_question", "errors", "acceptance")}
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
