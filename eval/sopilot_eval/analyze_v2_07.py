"""V2-07 analysis over a dev run and a test run of the same config file.

    python -m sopilot_eval.analyze_v2_07 --dev results/<dev_run> --test results/<test_run> --out results/<test_run>/analysis

* tables per config and per group (lang x same/cross-lingual, query_types, subset, tags) with 95%
  bootstrap CIs (2000 draws, seed 0). Resampling is by ``intent_id`` cluster: the VI and EN
  phrasings of one intent share evidence and are not independent;
* paired differences against ``dense`` and ``hybrid`` (same questions), with the number of questions
  where the config is better / worse;
* RQ1b: ``cross_lingual_bm25_factor`` picked on dev (best cross-lingual ``span_recall@5``), shown on test;
* RQ3: per gated config, threshold picked on dev by the pre-declared rule "minimise
  false_refusal + false_answer, ties -> the lower threshold", then measured on test.

Nothing here writes service configuration; thresholds are proposals for the owner.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

import numpy as np

METRICS = ("span_recall@5", "full@5", "any@5", "span_recall@10", "full@10", "mrr_span", "hit@5")
SEED, DRAWS = 0, 2000


def _rows(run: Path) -> dict[str, list[dict]]:
    by = defaultdict(list)
    for line in (run / "per_question.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            by[r["config"]].append(r)
    return by


def _ci(values: list[float], clusters: list[str] | None = None) -> tuple[float, float, float]:
    """Mean and 95% bootstrap CI; with ``clusters``, whole clusters are resampled (ratio of sums)."""
    a = np.asarray(values, dtype=float)
    if not len(a):
        return (float("nan"),) * 3
    rng = np.random.default_rng(SEED)
    if clusters is None:
        boots = a[rng.integers(0, len(a), (DRAWS, len(a)))].mean(axis=1)
    else:
        keys = sorted(set(clusters))
        index = {k: i for i, k in enumerate(keys)}
        sums, counts = np.zeros(len(keys)), np.zeros(len(keys))
        for v, c in zip(a, clusters):
            sums[index[c]] += v
            counts[index[c]] += 1
        draw = rng.integers(0, len(keys), (DRAWS, len(keys)))
        boots = sums[draw].sum(axis=1) / counts[draw].sum(axis=1)
    return float(a.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def _cluster(r: dict) -> str:
    return r.get("intent_id") or r["id"]


def _groups(r: dict) -> list[str]:
    lingual = "cross" if r["cross_lingual"] else "same"
    g = ["all", f"lingual={lingual}", f"lang={r['lang']}&{lingual}"] + [f"type={t}" for t in r["query_types"]]
    if r.get("subset"):
        g += [f"subset={r['subset']}", f"subset={r['subset']}&{lingual}"]
    return g + [f"tag={t}" for t in r.get("tags", [])]


def summarize(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["answerable"]]
    out: dict[str, dict] = {}
    for g in sorted({g for r in ans for g in _groups(r)}):
        sub = [r for r in ans if g in _groups(r)]
        out[g] = {"n": len(sub), "n_intents": len({_cluster(r) for r in sub}),
                  **{m: _ci([r[m] for r in sub], [_cluster(r) for r in sub]) for m in METRICS if m in sub[0]}}
    return out


def paired(rows_a: list[dict], rows_b: list[dict], metric: str, group: str = "all") -> dict:
    """Mean of (a - b) over the same answerable questions, intent-cluster bootstrap CI, wins/losses."""
    b = {r["id"]: r for r in rows_b}
    pairs = [(r[metric] - b[r["id"]][metric], _cluster(r)) for r in rows_a
             if r["answerable"] and group in _groups(r)]
    diffs = [d for d, _ in pairs]
    mean, lo, hi = _ci(diffs, [c for _, c in pairs])
    return {"n": len(diffs), "mean": mean, "lo": lo, "hi": hi,
            "better": sum(d > 0 for d in diffs), "worse": sum(d < 0 for d in diffs)}


def sweep(rows: list[dict], t: float) -> tuple[float, float]:
    ans = [r["gate_score"] for r in rows if r["answerable"]]
    neg = [r["gate_score"] for r in rows if not r["answerable"]]
    fr = sum(s < t for s in ans) / len(ans) if ans else 0.0
    fa = sum(s >= t for s in neg) / len(neg) if neg else 0.0
    return fr, fa


def pick_threshold(rows: list[dict]) -> dict:
    scores = sorted({r["gate_score"] for r in rows})
    cands = [scores[0]] + [(a + b) / 2 for a, b in pairwise(scores)] + [np.nextafter(scores[-1], np.inf)]
    best = min(cands, key=lambda t: (sum(sweep(rows, t)), t))
    fr, fa = sweep(rows, best)
    return {"threshold": float(best), "false_refusal": fr, "false_answer": fa}


def analyze(dev: Path, test: Path) -> dict:
    dev_rows, test_rows = _rows(dev), _rows(test)
    result: dict = {"dev_run": dev.name, "test_run": test.name, "configs": {}, "paired_vs_dense": {},
                    "paired_vs_hybrid": {}, "rq3": {}}
    for name, rows in test_rows.items():
        result["configs"][name] = {"test": summarize(rows), "dev": summarize(dev_rows.get(name, []))}
    pair_groups = ["all", "lingual=same", "lingual=cross"]
    if any(r.get("subset") for rows in test_rows.values() for r in rows):
        pair_groups += ["subset=v1", "subset=v2", "subset=v2&same", "subset=v2&cross"]
    for base, key in (("dense", "paired_vs_dense"), ("hybrid", "paired_vs_hybrid")):
        if base not in test_rows:
            continue
        for name, rows in test_rows.items():
            if name == base:
                continue
            result[key][name] = {
                g: {m: paired(rows, test_rows[base], m, g) for m in ("span_recall@5", "full@5", "mrr_span")}
                for g in pair_groups
            }
    xl = [n for n in ("hybrid", "hybrid-xl0.3", "hybrid-xl0") if n in dev_rows]
    if xl:
        def dev_cross(n: str) -> tuple[float, float]:
            s = summarize(dev_rows[n])
            return (s.get("lingual=cross", {}).get("span_recall@5", (0,))[0], s["all"]["span_recall@5"][0])

        ranking = sorted(xl, key=lambda n: (dev_cross(n), n == "hybrid"), reverse=True)
        result["rq1b"] = {"dev_cross_span_recall@5": {n: dev_cross(n) for n in xl}, "picked_on_dev": ranking[0]}
    for name, rows in test_rows.items():
        if not rows or rows[0]["gate_score"] is None or name not in dev_rows:
            continue
        chosen = pick_threshold(dev_rows[name])
        fr, fa = sweep(rows, chosen["threshold"])
        oracle = pick_threshold(rows)
        result["rq3"][name] = {
            "dev": chosen,
            "test_at_dev_threshold": {"false_refusal": fr, "false_answer": fa},
            "test_oracle_for_reference": oracle,
            "test_n_answerable": sum(r["answerable"] for r in rows),
            "test_n_unanswerable": sum(not r["answerable"] for r in rows),
            "dev_n_unanswerable": sum(not r["answerable"] for r in dev_rows[name]),
            "test_gate_answerable_mean": float(np.mean([r["gate_score"] for r in rows if r["answerable"]])),
            "test_gate_unanswerable_mean": float(np.mean([r["gate_score"] for r in rows if not r["answerable"]])),
        }
    return result


def fmt(ci) -> str:
    m, lo, hi = ci
    return f"{m:.3f} [{lo:.2f}, {hi:.2f}]"


def to_markdown(res: dict) -> str:
    lines = [f"# V2-07 analysis: dev `{res['dev_run']}`, test `{res['test_run']}`", ""]
    cols = ("span_recall@5", "full@5", "any@5", "full@10", "mrr_span", "hit@5")
    for split in ("test", "dev"):
        lines += [f"## {split}: by config and group (mean [95% bootstrap CI])", "",
                  "| config | group | n (intents) | " + " | ".join(cols) + " |", "|---|---|---|" + "---|" * len(cols)]
        for name, d in res["configs"].items():
            for g, s in d[split].items():
                if g.startswith("type=") and split == "dev":
                    continue
                lines.append(f"| {name} | {g} | {s['n']} ({s.get('n_intents', '')}) | "
                             + " | ".join(fmt(s[c]) if c in s else "" for c in cols) + " |")
        lines.append("")
    for key, base in (("paired_vs_dense", "dense"), ("paired_vs_hybrid", "hybrid")):
        if not res.get(key):
            continue
        lines += [f"## test: paired difference vs {base} (config - {base}; better/worse = questions)", "",
                  "| config | group | n | Δspan_recall@5 (better/worse) | Δfull@5 | Δmrr_span |", "|---|---|---|---|---|---|"]
        for name, d in res[key].items():
            for g, m in d.items():
                a, b, c = m["span_recall@5"], m["full@5"], m["mrr_span"]
                lines.append(f"| {name} | {g} | {a['n']} | {a['mean']:+.3f} [{a['lo']:+.2f}, {a['hi']:+.2f}] "
                             f"({a['better']}/{a['worse']}) | {b['mean']:+.3f} [{b['lo']:+.2f}, {b['hi']:+.2f}] | "
                             f"{c['mean']:+.3f} [{c['lo']:+.2f}, {c['hi']:+.2f}] |")
        lines.append("")
    if "rq1b" in res:
        lines += ["", "## RQ1b: cross_lingual_bm25_factor on dev", "",
                  "| config | dev cross span_recall@5 | dev all span_recall@5 |", "|---|---|---|"]
        for n, (c, a) in res["rq1b"]["dev_cross_span_recall@5"].items():
            lines.append(f"| {n} | {c:.3f} | {a:.3f} |")
        lines.append(f"\nPicked on dev: `{res['rq1b']['picked_on_dev']}`")
    lines += ["", "## RQ3: threshold picked on dev, measured on test", "",
              "| config | dev threshold | dev FR | dev FA | test FR | test FA | test oracle t (FR/FA) | n test ans/neg |",
              "|---|---|---|---|---|---|---|---|"]
    for name, r in res["rq3"].items():
        d, t, o = r["dev"], r["test_at_dev_threshold"], r["test_oracle_for_reference"]
        lines.append(f"| {name} | {d['threshold']:.4f} | {d['false_refusal']:.3f} | {d['false_answer']:.3f} | "
                     f"{t['false_refusal']:.3f} | {t['false_answer']:.3f} | {o['threshold']:.4f} "
                     f"({o['false_refusal']:.3f}/{o['false_answer']:.3f}) | {r['test_n_answerable']}/{r['test_n_unanswerable']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", type=Path, required=True)
    ap.add_argument("--test", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    res = analyze(a.dev, a.test)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "analysis.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    (a.out / "analysis.md").write_text(to_markdown(res), encoding="utf-8")


if __name__ == "__main__":
    main()
