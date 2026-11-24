from __future__ import annotations

import math


def _page_hit(chunk, target: dict) -> bool:
    """Same document and, when the target lists pages, a chunk page inside them.
    A docproc chunk spans ``page..page_end``; a character chunk has one page."""
    if chunk.doc != target["doc"]:
        return False
    if not target.get("pages"):
        return True
    if chunk.page is None:
        return False
    last = getattr(chunk, "page_end", None) or chunk.page
    return any(chunk.page <= p <= last for p in target["pages"])


def is_hit(chunk, expected: list[dict]) -> int | None:
    """Index of the expected target this chunk satisfies, else None. Target = {doc, pages?}."""
    for n, t in enumerate(expected):
        if _page_hit(chunk, t):
            return n
    return None


def retrieval_metrics(ranked_chunks: list, expected: list[dict], ks=(1, 3, 5, 10)) -> dict:
    """Per-question metrics. recall@k = share of expected targets covered by the top k chunks."""
    if not expected or any(k <= 0 for k in ks):
        raise ValueError("answerable metrics require targets and positive k")
    hits = [{n for n, t in enumerate(expected) if _page_hit(c, t)} for c in ranked_chunks]
    out = {}
    for k in ks:
        covered = set().union(*hits[:k])
        out[f"recall@{k}"] = len(covered) / len(expected)
        out[f"hit@{k}"] = 1.0 if covered else 0.0
    first = next((r for r, h in enumerate(hits, 1) if h), None)
    out["mrr"] = 1.0 / first if first else 0.0
    seen = set()
    dcg = 0.0
    for r, targets in enumerate(hits[:10], 1):
        # Overlapping chunks from one target must not repeatedly earn relevance.
        if targets - seen:
            dcg += 1.0 / math.log2(r + 1)
        seen.update(targets)
    ideal = sum(1.0 / math.log2(r + 1) for r in range(1, min(len(expected), 10) + 1))
    out["ndcg@10"] = dcg / ideal if ideal else 0.0
    return out


def refusal_sweep(answerable_scores: list[float], unanswerable_scores: list[float], steps: int = 25) -> list[dict]:
    """RQ3 retrieval-level proxy: refuse when top score < t.
    false_refusal = answerable refused; false_answer = unanswerable answered."""
    if steps <= 0:
        raise ValueError("steps must be positive")
    allv = sorted(answerable_scores + unanswerable_scores)
    if not all(math.isfinite(s) for s in allv):
        raise ValueError("gate scores must be finite")
    if not allv:
        return []
    lo, hi = allv[0], allv[-1]
    rows = []
    thresholds = [lo + (hi - lo) * i / steps for i in range(steps + 1)]
    thresholds.append(math.nextafter(hi, math.inf))
    for t in thresholds:
        fr = sum(s < t for s in answerable_scores) / len(answerable_scores) if answerable_scores else 0.0
        fa = sum(s >= t for s in unanswerable_scores) / len(unanswerable_scores) if unanswerable_scores else 0.0
        rows.append({"threshold": t, "false_refusal": round(fr, 4), "false_answer": round(fa, 4)})
    return rows


SPAN_COVER = 0.5  # a span counts as retrieved when the top-k chunks cover >= half of its characters


def _covered(span: dict, chunks: list) -> float:
    """Share of the span's characters covered by the union of ``chunks`` of the same document."""
    s, e = span["start_char"], span["end_char"]
    parts = sorted(
        (max(s, c.char_start), min(e, c.char_end))
        for c in chunks
        if c.doc_id == span["doc_id"] and c.char_start is not None and c.char_start < e and c.char_end > s
    )
    total, cur = 0, s
    for a, b in parts:
        a = max(a, cur)
        if b > a:
            total += b - a
            cur = b
    return total / (e - s) if e > s else 0.0


def span_metrics(ranked_chunks: list, evidence_sets: list[list[str]], spans: dict, ks=(1, 3, 5, 10)) -> dict:
    """Span-gold metrics over docproc chunks (``char_start``/``char_end`` in the canonical text).

    ``evidence_sets`` are OR alternatives of AND span lists. Per k, take the best alternative:
    ``span_recall@k`` = share of its spans covered by the top k; ``full@k`` = 1 when every span of
    some alternative is covered (the context holds all required evidence); ``any@k`` = 1 when at
    least one gold span is covered. ``mrr_span`` uses the first chunk covering any gold span.
    """
    if not evidence_sets or any(k <= 0 for k in ks):
        raise ValueError("answerable metrics require evidence sets and positive k")
    out = {}
    for k in ks:
        top = ranked_chunks[:k]
        best = 0.0
        for es in evidence_sets:
            covered = sum(_covered(spans[sid], top) >= SPAN_COVER for sid in es)
            best = max(best, covered / len(es))
        anyc = any(_covered(spans[sid], top) >= SPAN_COVER for es in evidence_sets for sid in es)
        out[f"span_recall@{k}"] = best
        out[f"full@{k}"] = 1.0 if best == 1.0 else 0.0
        out[f"any@{k}"] = 1.0 if anyc else 0.0
    gold = {sid for es in evidence_sets for sid in es}
    first = next(
        (r for r, c in enumerate(ranked_chunks, 1) if any(_covered(spans[sid], [c]) > 0 for sid in gold)),
        None,
    )
    out["mrr_span"] = 1.0 / first if first else 0.0
    return out
