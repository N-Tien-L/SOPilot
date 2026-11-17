"""Corpus-specific routing report for V2-44: rule layer alone, then rules + SetFit classifier.

Reads ``eval/datasets/routing/corpus-test.jsonl`` (real questions of ``sop-main-v2`` plus drafted
non-SOP rows) and runs the service code: the deterministic rule steps, then
``sopilot_ai.qa.setfit_router`` with the spec of ``config/models.yaml``. Reports, separately:

- the rule layer on its own: genuine ``sop_question`` / ``followup`` rows that the rules turn into a
  refusal, a template or "not understood", each with its rule id;
- the classifier: SOP/follow-up rows answered by a template ("costly"), rows that would only get a
  disclaimer or an out-of-scope candidate, and the routed-template accuracy, each with and without
  history;
- latency of the classifier call and resident memory after loading.

    cd eval; uv run --extra local python -m sopilot_eval.routing_corpus_report --artifact <dir>

The set is never used for training or tuning. Its drafted non-SOP rows need the owner's review.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from sopilot_ai.providers.registry import ModelsConfig
from sopilot_ai.qa import router, setfit_router
from sopilot_ai.qa.pipeline import DecisionKind, PipelineContext, run_steps
from sopilot_ai.qa.steps import deterministic_steps

from sopilot_eval.routing import (
    EVAL_ROOT,
    REPO_ROOT,
    TEMPLATE_LABELS,
    load_dataset,
    load_vocabulary,
)

DATASET = EVAL_ROOT / "datasets" / "routing" / "corpus-test.jsonl"
DEFAULT_ARTIFACT = EVAL_ROOT / "results/routing/setfit-router-model-histaug/setfit-router"
RETRIEVAL = {"sop_question", "followup"}


async def _rule(text: str, vocab: frozenset[str]) -> tuple[Any, PipelineContext]:
    async def known(words: Any) -> set[str]:
        return {w for w in words if w in vocab}

    ctx = PipelineContext(question=text, known_terms=known)
    return await run_steps(deterministic_steps(), ctx), ctx


def _rss_mb() -> float | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                    ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    kernel, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.WorkingSetSize / 2**20)


def _answer_like(prev: str, lang: str, k: int) -> str:
    """A realistic assistant answer whose first sentence is ``prev`` (styles rotate with ``k``)."""
    head = prev.rstrip(".!? ")
    tail = ("Nếu cần thêm thông tin, hãy hỏi tiếp." if lang == "vi"
            else "Ask again if you need more detail.")
    styles = (
        f"{head} [1]. Ngoài ra cần lưu ý các điều kiện áp dụng [2]. {tail}",
        f"## Trả lời\n\n{head} [1][2].\n\n- Bước 1 [1]\n- Bước 2 [2]",
        f"1. {head} [1]\n2. Sau đó kiểm tra lại [2].",
        f"**{head}** [1, 2]\n\n{tail}",
        f"1. {head} [1]\n2. Chờ duyệt [2]\n\n{tail}",  # list first, prose after
        f"**Trả lời**\n\n{head} [1].\n\n* Chi tiết [2]",  # bold pseudo-heading, `*` bullets
        f"| Bước | Nội dung |\n|---|---|\n| 1 | Nộp đơn |\n\n{head} [1].",  # table first
    )
    return styles[k % len(styles)]


def _history_check(rows: list[dict[str, Any]], classifier: Any, vocab: frozenset[str]) -> dict[str, Any]:
    """The history rows again, with the previous message built by the service's own
    ``previous_message()`` from answer-like history (markers, headings, lists, long answers)."""
    from sopilot_ai.conversations.steps import QAContext, classify_question

    same = differ = cut = 0
    swaps: Counter = Counter()
    outcome: Counter = Counter()
    examples: list[dict[str, str]] = []
    for k, row in enumerate(r for r in rows if r.get("previous_turn")):
        decision, ctx = asyncio.run(_rule(row["text"], vocab))
        if decision.kind is not DecisionKind.CONTINUE:
            outcome[f"{row['intent']}->rule"] += 1
            continue
        prev = row["previous_turn"]
        answer = _answer_like(prev, row.get("lang", "vi"), k)
        built = setfit_router.previous_message([("câu hỏi trước", answer)],
                                               classifier.spec.previous_max_chars)
        exact = (built or "").rstrip(".!? ") == prev.rstrip(".!? ")
        if not exact and len(prev) >= classifier.spec.previous_max_chars - 5:
            cut += 1
        elif not exact and len(examples) < 5:
            examples.append({"intended": prev[:80], "built": (built or "")[:80]})
        raw = classifier.classify(ctx.text, prev)
        c = QAContext(question=row["text"], lang=row.get("lang", "vi"))
        c.text = ctx.text
        c.history = [("câu hỏi trước", answer)]
        got = asyncio.run(classify_question(classifier, c, "check"))
        assert got is not None
        same += got.label == raw.label
        differ += got.label != raw.label
        if got.label != raw.label:
            swaps[f"{raw.label}->{got.label}"] += 1
        outcome[f"{row['intent']}->{got.action}"] += 1
        if row["intent"] in RETRIEVAL and got.action == router.ACTION_TEMPLATE:
            outcome["SOP_ANSWERED_BY_TEMPLATE"] += 1
    return {"rows_checked": same + differ, "same_label_as_clean_previous_turn": same,
            "label_changed": differ, "changes": dict(swaps), "previous_message_cut_by_limit": cut,
            "previous_message_differs_otherwise": examples, "outcomes": dict(outcome)}


def _pct(values: list[float], p: int) -> float:
    return round(float(np.percentile(values, p)), 1)


def run(artifact: Path) -> dict[str, Any]:
    rows = load_dataset(DATASET)
    vocab = load_vocabulary(REPO_ROOT / "eval/datasets/sop-main-v2/corpus")
    models = ModelsConfig.load(REPO_ROOT / "services/ai-service/config/models.yaml")
    spec = replace(models.router_classifier(REPO_ROOT / "services/ai-service"), artifact_dir=artifact)
    rss_before = _rss_mb()
    t0 = time.perf_counter()
    classifier = setfit_router.load_classifier(spec)
    load_s = round(time.perf_counter() - t0, 1)
    classifier.classify("khởi động")
    rss_after = _rss_mb()

    rule_hits: list[dict[str, Any]] = []
    cls: dict[str, Counter] = {"no_history": Counter(), "with_history": Counter()}
    wrong: list[dict[str, Any]] = []
    ms: list[float] = []
    for row in rows:
        decision, ctx = asyncio.run(_rule(row["text"], vocab))
        hist = "with_history" if row.get("previous_turn") else "no_history"
        intent = row["intent"]
        if decision.kind is not DecisionKind.CONTINUE:
            if intent in RETRIEVAL:
                rule_hits.append({"id": row["id"], "intent": intent, "text": row["text"],
                                  "rule_id": decision.rule_id, "outcome": decision.outcome,
                                  "template": decision.template_key})
            cls[hist][f"rule_decided:{intent}"] += 1
            continue
        started = time.perf_counter()
        verdict = classifier.classify(ctx.text, row.get("previous_turn"))
        ms.append((time.perf_counter() - started) * 1000)
        key = f"{intent}->{verdict.action}"
        cls[hist][key] += 1
        if intent in RETRIEVAL and verdict.action == router.ACTION_TEMPLATE:
            wrong.append({"id": row["id"], "intent": intent, "text": row["text"],
                          "label": verdict.label, "confidence": round(verdict.confidence, 3)})
        if intent in TEMPLATE_LABELS and verdict.label != intent:
            wrong.append({"id": row["id"], "intent": intent, "text": row["text"],
                          "label": verdict.label, "action": verdict.action,
                          "confidence": round(verdict.confidence, 3)})
    sop = [r for r in rows if r["intent"] in RETRIEVAL]
    return {
        "dataset": str(DATASET.relative_to(REPO_ROOT)), "rows": len(rows),
        "by_intent": dict(Counter(r["intent"] for r in rows)),
        "with_history": sum(bool(r.get("previous_turn")) for r in rows),
        "rule_layer": {"retrieval_rows": len(sop), "turned_away_by_rules": len(rule_hits),
                       "hits": rule_hits},
        "classifier": {name: dict(c) for name, c in cls.items()},
        "retrieval_rows_answered_by_template": [w for w in wrong if w["intent"] in RETRIEVAL],
        "template_rows_misrouted": [w for w in wrong if w["intent"] in TEMPLATE_LABELS],
        "history_via_previous_message": _history_check(rows, classifier, vocab),
        "latency_ms": {"n": len(ms), "p50": _pct(ms, 50), "p95": _pct(ms, 95), "max": _pct(ms, 100)},
        "memory_mb": {"before_load": rss_before, "after_load_and_warmup": rss_after},
        "load_s": load_s,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()
    result = run(args.artifact)
    out = EVAL_ROOT / "results" / "routing" / "corpus-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
