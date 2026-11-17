"""Agreement between a grader and the judge (V2-37 D, E): Cohen's kappa with a bootstrap interval.

Two graders label the same answers on an ordered scale (``correct`` > ``partial`` > ``wrong``, or
``supported`` > ``partial`` > ``unsupported``). Report the plain kappa and the linearly weighted one
(a ``partial`` against ``wrong`` is a smaller disagreement than ``correct`` against ``wrong``).

CLI (from ``eval/``)::

    uv run python -m sopilot_eval.agreement --rows per_question.jsonl --grades grades.jsonl --field correctness

``grades.jsonl`` holds one ``{"id": ..., "expand": true, "correctness": ..., "verdict": ...}`` per graded answer; the
rows are matched by ``id`` and ``expand`` (``true`` or ``false``) with the lines of ``per_question.jsonl``. State in the report
who graded: a kappa against an LLM grader is not a kappa against a human.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

SCALES = {"correctness": ("wrong", "partial", "correct"), "verdict": ("unsupported", "partial", "supported")}


def cohens_kappa(a: Sequence[str], b: Sequence[str], scale: Sequence[str], *, weighted: bool = False
                 ) -> float | None:
    """Cohen's kappa of two label lists over ``scale`` (ordered); ``None`` when chance agreement is 1."""
    if len(a) != len(b) or not a:
        raise ValueError("two non-empty label lists of the same length are needed")
    index = {label: i for i, label in enumerate(scale)}
    n, k = len(a), len(scale)

    def weight(i: int, j: int) -> float:  # disagreement weight, 0 on the diagonal
        if not weighted:
            return float(i != j)
        return abs(i - j) / (k - 1)

    pairs = Counter((index[x], index[y]) for x, y in zip(a, b, strict=True))
    row, col = Counter(index[x] for x in a), Counter(index[y] for y in b)
    observed = sum(weight(i, j) * c for (i, j), c in pairs.items()) / n
    expected = sum(weight(i, j) * row[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    if expected == 0:
        return None
    return 1.0 - observed / expected


def bootstrap_ci(a: Sequence[str], b: Sequence[str], scale: Sequence[str], *, weighted: bool = False,
                 rounds: int = 2000, seed: int = 7) -> tuple[float, float] | None:
    """95% percentile interval of kappa over resampled answers (fixed seed)."""
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(rounds):
        pick = [rng.randrange(len(a)) for _ in a]
        value = cohens_kappa([a[i] for i in pick], [b[i] for i in pick], scale, weighted=weighted)
        if value is not None:
            stats.append(value)
    if len(stats) < rounds // 2:
        return None
    stats.sort()
    return stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1]


def agreement(a: Sequence[str], b: Sequence[str], scale: Sequence[str]) -> dict[str, object]:
    return {
        "n": len(a), "exact_agreement": sum(x == y for x, y in zip(a, b, strict=True)) / len(a),
        "kappa": cohens_kappa(a, b, scale), "kappa_ci95": bootstrap_ci(a, b, scale),
        "kappa_weighted": cohens_kappa(a, b, scale, weighted=True),
        "kappa_weighted_ci95": bootstrap_ci(a, b, scale, weighted=True),
        "confusion": {f"{x}|{y}": c for (x, y), c in sorted(Counter(zip(a, b, strict=True)).items())},
    }


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rows", type=Path, required=True, help="per_question.jsonl of an answers run")
    ap.add_argument("--grades", type=Path, required=True, help="grades.jsonl of the other grader")
    ap.add_argument("--field", choices=sorted(SCALES), required=True)
    a = ap.parse_args()
    judge = {f"{r['id']}|{r['expand']}": r[a.field] for r in _read(a.rows) if r.get(a.field)}
    other = {f"{g['id']}|{g['expand']}": g[a.field] for g in _read(a.grades) if g.get(a.field)}
    ids = sorted(set(judge) & set(other))
    if not ids:
        raise SystemExit("no answer is graded by both")
    report = agreement([other[i] for i in ids], [judge[i] for i in ids], SCALES[a.field])
    report.update({"field": a.field, "ids": ids})
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
