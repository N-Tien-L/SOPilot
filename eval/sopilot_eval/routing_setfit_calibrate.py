"""Offline temperature scaling for a finished SetFit run (needs ``oof.npy`` and ``per_question.jsonl``).

SetFit's logistic head is over-confident near 0.8-0.9, so a confidence threshold cannot separate sure from
unsure rows. Here one temperature ``T`` is fitted on the dev out-of-fold probabilities by minimum negative
log-likelihood (no routing metric, no test data), probabilities become ``softmax(log p / T)``, then the
threshold is picked on dev exactly as in ``routing_setfit_remote`` and the frozen test split is scored once.

Run from ``eval/``::

    uv run python -m sopilot_eval.routing_setfit_calibrate --run setfit-bge-m3-pool447-hist-test
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from sopilot_eval.routing import EVAL_ROOT, LABELS, load_dataset
from sopilot_eval.routing_setfit_remote import (
    CONF_GRID,
    DATA,
    DESIGNS,
    IDX,
    pick_threshold,
    score,
)

T_GRID = [round(0.5 + 0.1 * i, 1) for i in range(46)]  # 0.5 .. 5.0


def scale(p: np.ndarray, temperature: float) -> np.ndarray:
    z = np.log(np.clip(p, 1e-9, 1.0)) / temperature
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-9, 1.0)).mean())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--run", required=True, help="folder name under eval/results/routing")
    ap.add_argument("--no-candidates", action="store_true")
    ap.add_argument("--defer-extra", nargs="*", default=[],
                    help="labels added to the two_group deferred set (scored as design two_group+)")
    args = ap.parse_args()
    run = EVAL_ROOT / "results" / "routing" / args.run
    dev = load_dataset(DATA / "train-pool.jsonl")
    if args.no_candidates:
        dev = [r for r in dev if r.get("source") != "candidate"]
    test = load_dataset(DATA / "test.jsonl")
    oof = np.load(run / "oof.npy")
    per = {x["id"]: x for x in map(json.loads, (run / "per_question.jsonl").read_text(encoding="utf-8").splitlines())}
    probs = np.array([per[r["id"]]["proba"] for r in test])
    y = np.array([IDX[r["intent"]] for r in dev])

    best_t = min(T_GRID, key=lambda t: nll(scale(oof, t), y))
    print(f"T = {best_t} (dev OOF NLL {nll(oof, y):.3f} -> {nll(scale(oof, best_t), y):.3f})")
    designs = dict(DESIGNS)
    if args.defer_extra:
        designs["two_group+"] = DESIGNS["two_group"] | frozenset(args.defer_extra)
    for name, t in (("raw", 1.0), ("calibrated", best_t)):
        o, p = scale(oof, t), scale(probs, t)
        print(f"\n{name} (T={t}); top-1 confidence p50/p90 on test: "
              f"{np.percentile(p.max(1), 50):.2f}/{np.percentile(p.max(1), 90):.2f}")
        for d, deferred in designs.items():
            ds, mc = pick_threshold(dev, o, deferred)
            ts = score(test, p, mc, deferred)
            print(f"  {d:9s} min_conf {mc:<5} dev {ds['routed_ok']}/{ds['routable']} costly {ds['costly']}"
                  f" | test {ts['routed_ok']}/{ts['routable']} costly {ts['costly']}")
    _ = (CONF_GRID, LABELS)


if __name__ == "__main__":
    main()
