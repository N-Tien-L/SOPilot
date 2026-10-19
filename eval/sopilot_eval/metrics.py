from __future__ import annotations

import math


def is_hit(chunk, expected: list[dict]) -> int | None:
    """Index of the expected target this chunk satisfies, else None. Target = {doc, pages?}."""
    for n, t in enumerate(expected):
        if chunk.doc == t["doc"] and (not t.get("pages") or chunk.page in t["pages"]):
            return n
    return None


def retrieval_metrics(ranked_chunks: list, expected: list[dict], ks=(1, 3, 5, 10)) -> dict:
    """Per-question metrics. recall@k = share of expected targets covered by the top k chunks."""
    hits = [is_hit(c, expected) for c in ranked_chunks]
    out = {}
    for k in ks:
        covered = {h for h in hits[:k] if h is not None}
        out[f"recall@{k}"] = len(covered) / len(expected)
        out[f"hit@{k}"] = 1.0 if covered else 0.0
    first = next((r for r, h in enumerate(hits, 1) if h is not None), None)
    out["mrr"] = 1.0 / first if first else 0.0
    dcg = sum(1.0 / math.log2(r + 1) for r, h in enumerate(hits[:10], 1) if h is not None)
    ideal = sum(1.0 / math.log2(r + 1) for r in range(1, min(len(expected), 10) + 1))
    out["ndcg@10"] = dcg / ideal if ideal else 0.0
    return out


def refusal_sweep(answerable_scores: list[float], unanswerable_scores: list[float], steps: int = 25) -> list[dict]:
    """RQ3 retrieval-level proxy: refuse when top score < t.
    false_refusal = answerable refused; false_answer = unanswerable answered."""
    allv = sorted(answerable_scores + unanswerable_scores)
    if not allv:
        return []
    lo, hi = allv[0], allv[-1]
    rows = []
    for i in range(steps + 1):
        t = lo + (hi - lo) * i / steps
        fr = sum(s < t for s in answerable_scores) / len(answerable_scores) if answerable_scores else 0.0
        fa = sum(s >= t for s in unanswerable_scores) / len(unanswerable_scores) if unanswerable_scores else 0.0
        rows.append({"threshold": round(t, 4), "false_refusal": round(fr, 4), "false_answer": round(fa, 4)})
    return rows
