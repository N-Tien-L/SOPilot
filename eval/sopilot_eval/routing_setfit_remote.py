"""SetFit router experiment against the Kaggle server ``eval/kaggle/setfit_server.ipynb``.

Training rows: ``train-pool.jsonl`` (dev + dev-extra + accepted candidates; ``--no-candidates`` keeps the
187-row pool from before the 2026-11-17 merge) and the router exemplars unless ``--no-exemplars``. Folds
are stratified by intent and, for ``off_topic``, by ``subtype``. The confidence threshold is
picked on dev with stratified k-fold out-of-fold probabilities (zero costly errors, i.e. no
``sop_question`` / ``followup`` routed away); then one model is trained on all rows and the test split
is predicted once, one question per call so ``server_ms`` is the per-question latency. Two designs are
scored, each with its own dev-picked threshold: ``flat`` (all 14 labels routed before retrieval) and
``two_group`` (``DEFERRED`` corpus-dependent labels left to retrieval). ``--save`` keeps the final model
in ``/kaggle/working`` on the server for download.

Run from ``eval/``::

    $env:ROUTER_API_TOKEN = "<token>"
    uv run python -m sopilot_eval.routing_setfit_remote --url https://<name>.trycloudflare.com --with-history
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import urllib.error
from collections import Counter
from typing import Any

import numpy as np
import yaml

from sopilot_eval.routing import (
    EVAL_ROOT,
    EXPECTED,
    LABELS,
    RAG,
    REPO_ROOT,
    load_dataset,
)
from sopilot_eval.routing_remote import _request, _stats, connect, model_input

DATA = REPO_ROOT / "eval/datasets/routing"
EXEMPLARS = REPO_ROOT / "services/ai-service/src/sopilot_ai/qa/router_exemplars.yaml"
BASELINE = EVAL_ROOT / "results/routing/routing-rules-router-test/per_question.jsonl"
CONF_GRID = [round(x * 0.05, 2) for x in range(20)]  # 0.00 .. 0.95
COSTLY = ("sop_question", "followup")
# Corpus-dependent labels: whether a question is in scope depends on the workspace corpus, so in the
# two-group design they are not routed before retrieval (retrieval and its gate decide).
DEFERRED = frozenset({"off_topic", "legal_medical", "personal_data"})
DESIGNS = {"flat": frozenset(), "two_group": DEFERRED}
IDX = {k: i for i, k in enumerate(LABELS)}


TRANSIENT = (502, 503, 504, 520, 522, 524, 530)


def _poll(url: str, token: str, timeout: float, patience: float = 900.0) -> dict[str, Any]:
    """GET that survives tunnel hiccups (Cloudflare 502/504, resets) for up to ``patience`` seconds.

    Training keeps running on the server while the tunnel blips, so a failed poll is not a failed job.
    """
    start = time.monotonic()
    while True:
        try:
            return _request(url, token, None, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT:
                raise
            err: Exception = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            err = exc
        if time.monotonic() - start > patience:
            sys.exit(f"server unreachable for {patience:.0f} s ({err}); is the Kaggle session alive?")
        print(f"  poll failed ({err}); retrying", file=sys.stderr)
        time.sleep(15)


def train(base: str, token: str, texts: list[str], labels: list[int], args: argparse.Namespace) -> str:
    job = _request(f"{base}/train", token, {
        "texts": texts, "labels": labels, "model_id": args.model, "num_iterations": args.iterations,
        "num_epochs": args.epochs, "batch_size": args.batch_size, "max_seq_length": 128,
        "seed": args.seed}, args.timeout)["job"]
    while True:
        time.sleep(5)
        st = _poll(f"{base}/job/{job}", token, args.timeout)
        if st["state"] == "done":
            print(f"  trained {len(texts)} rows in {st['train_s']} s", file=sys.stderr)
            return job
        if st["state"] == "failed":
            sys.exit(f"training failed on the server: {st.get('error')}")


def predict(base: str, token: str, job: str, texts: list[str], timeout: float
            ) -> tuple[np.ndarray, list[float]]:
    """Probabilities in ``LABELS`` order (absent classes get 0) and per-question server ms."""
    probs = np.zeros((len(texts), len(LABELS)))
    ms: list[float] = []
    for i in range(0, len(texts), 64):
        resp = _request(f"{base}/predict", token, {"job": job, "texts": texts[i:i + 64]}, timeout)
        for j, r in enumerate(resp["results"]):
            probs[i + j, resp["classes"]] = r["proba"]
            ms.append(r["server_ms"])
    return probs, ms


def route_of(p: np.ndarray, min_conf: float, deferred: frozenset[str] = frozenset()
             ) -> tuple[str, float, str]:
    i = int(p.argmax())
    intent, conf = LABELS[i], float(p[i])
    route = EXPECTED[intent] if conf >= min_conf and intent not in deferred else RAG
    return intent, conf, route


def score(rows: list[dict[str, Any]], probs: np.ndarray, min_conf: float,
          deferred: frozenset[str] = frozenset()) -> dict[str, int]:
    """Counts; ``routed_ok`` / ``routable`` cover the non-RAG labels the design routes before retrieval."""
    s = Counter()
    for row, p in zip(rows, probs, strict=True):
        intent, _, route = route_of(p, min_conf, deferred)
        want = EXPECTED[row["intent"]]
        s["costly"] += row["intent"] in COSTLY and route != RAG
        s["sop_misroute"] += row["intent"] == "sop_question" and route != RAG
        if want != RAG and row["intent"] not in deferred:
            s["routable"] += 1
            s["routed_ok"] += route == want
        s["intent_ok"] += intent == row["intent"]
    return s


def pick_threshold(rows: list[dict[str, Any]], oof: np.ndarray, deferred: frozenset[str]
                   ) -> tuple[dict[str, int], float]:
    """Highest dev routed_ok with zero costly errors (ties: intent accuracy)."""
    safe = [(score(rows, oof, mc, deferred), mc) for mc in CONF_GRID]
    safe = [(s, mc) for s, mc in safe if s["costly"] == 0]
    if not safe:
        return Counter(), 1.0
    return max(safe, key=lambda t: (t[0]["routed_ok"], t[0]["intent_ok"]))


def folds(labels: list[str], k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.array(labels)
    out = np.zeros(len(y), int)
    for c in np.unique(y):
        ids = rng.permutation(np.where(y == c)[0])
        out[ids] = np.arange(len(ids)) % k
    return out


def run_modal(args: argparse.Namespace, dev_texts: list[str], dev_labels: list[int], ex_texts: list[str],
              ex_labels: list[int], fold: np.ndarray, test_texts: list[str]
              ) -> tuple[np.ndarray, np.ndarray, list[float], Any, dict[str, Any]]:
    """Folds and the final model as parallel Modal jobs (``experiments/routing/modal_setfit_app.py``).

    Needs ``uv run --with modal`` (not a project dependency). Returns ``(oof, test_probs, ms, saved, health)``.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "modal_setfit_app", EVAL_ROOT / "experiments/routing/modal_setfit_app.py")
    app_mod = importlib.util.module_from_spec(spec)
    sys.modules["modal_setfit_app"] = app_mod
    spec.loader.exec_module(app_mod)

    hp = {"model_id": args.model, "num_iterations": args.iterations, "num_epochs": args.epochs,
          "batch_size": args.batch_size, "max_seq_length": 128, "seed": args.seed}
    jobs, held = [], []
    for f in range(args.folds):
        tr = [i for i in range(len(dev_texts)) if fold[i] != f]
        te = [i for i in range(len(dev_texts)) if fold[i] == f]
        held.append(te)
        jobs.append({**hp, "texts": [dev_texts[i] for i in tr] + ex_texts,
                     "labels": [dev_labels[i] for i in tr] + ex_labels,
                     "predict_texts": [dev_texts[i] for i in te]})
    jobs.append({**hp, "texts": dev_texts + ex_texts, "labels": dev_labels + ex_labels,
                 "predict_texts": test_texts, "per_question": True, "save": args.save,
                 "label_names": list(LABELS)})
    print(f"modal: {len(jobs)} jobs in parallel on {app_mod.GPU}", file=sys.stderr)
    with app_mod.app.run():
        results = list(app_mod.train_predict.map(jobs))
    oof = np.zeros((len(dev_texts), len(LABELS)))
    for te, r in zip(held, results[:-1], strict=True):
        oof[np.ix_(te, r["classes"])] = np.array(r["probas"])
        print(f"  fold trained in {r['train_s']} s on {r['gpu']}", file=sys.stderr)
    final = results[-1]
    probs = np.zeros((len(test_texts), len(LABELS)))
    probs[:, final["classes"]] = np.array(final["probas"])
    print(f"  final trained in {final['train_s']} s", file=sys.stderr)
    health = {"backend": "modal", "gpu": final["gpu"], "versions": app_mod.VERSIONS}
    return oof, probs, final["ms"], final["saved"], health


def run_kaggle(args: argparse.Namespace, base: str, token: str, dev: list[dict[str, Any]],
               dev_texts: list[str], dev_labels: list[int], ex_texts: list[str], ex_labels: list[int],
               fold: np.ndarray, test_texts: list[str]) -> tuple[Any, Any, np.ndarray, list[float], Any]:
    oof = np.zeros((len(dev), len(LABELS)))
    key = hashlib.sha1(json.dumps([args.model, args.with_history, args.no_exemplars, args.iterations,
                                   args.epochs, args.batch_size, args.seed, args.folds, args.augment_history,
                                   [r["id"] for r in dev]]).encode()).hexdigest()[:10]
    ckpt = EVAL_ROOT / "results" / "routing" / f".ckpt-setfit-{key}"
    ckpt.mkdir(parents=True, exist_ok=True)
    for f in range(args.folds):
        tr = [i for i in range(len(dev)) if fold[i] != f]
        te = [i for i in range(len(dev)) if fold[i] == f]
        done = ckpt / f"fold{f}.npy"
        if done.exists():  # a finished fold survives a crash later in the run
            oof[te] = np.load(done)
            print(f"fold {f + 1}/{args.folds} (cached)", file=sys.stderr)
            continue
        print(f"fold {f + 1}/{args.folds}", file=sys.stderr)
        job = train(base, token, [dev_texts[i] for i in tr] + ex_texts,
                    [dev_labels[i] for i in tr] + ex_labels, args)
        oof[te] = predict(base, token, job, [dev_texts[i] for i in te], args.timeout)[0]
        np.save(done, oof[te])
    picked = {d: pick_threshold(dev, oof, deferred) for d, deferred in DESIGNS.items()}

    print("final model", file=sys.stderr)
    job = train(base, token, dev_texts + ex_texts, dev_labels + ex_labels, args)
    predict(base, token, job, test_texts[:3], args.timeout)  # warm-up
    probs, ms = predict(base, token, job, test_texts, args.timeout)
    saved = _request(f"{base}/save", token, {"job": job, "label_names": list(LABELS)}, args.timeout) if args.save else None
    return oof, picked, probs, ms, saved


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--url", help="Kaggle tunnel URL (omit with --modal)")
    p.add_argument("--modal", action="store_true", help="train on Modal GPUs in parallel instead")
    p.add_argument("--model", default="BAAI/bge-m3")
    p.add_argument("--with-history", action="store_true")
    p.add_argument("--no-candidates", action="store_true")
    p.add_argument("--no-exemplars", action="store_true")
    p.add_argument("--augment-history", action="store_true",
                   help="with --with-history: give half of the training rows without a previous turn a random "
                        "one, so that a previous message is not a cue for followup / about_source")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--iterations", type=int, default=20, help="SetFit pairs per sample")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--name", default=None)
    p.add_argument("--save", action="store_true",
                   help="save the final model on the server (/kaggle/working) for download")
    p.add_argument("--timeout", type=float, default=90.0)
    args = p.parse_args()
    if not args.modal and not args.url:
        p.error("--url is required unless --modal is given")

    base, token, health = ("", "", {}) if args.modal else connect(args.url, args.timeout)
    dev = load_dataset(DATA / "train-pool.jsonl")
    if args.no_candidates:
        dev = [r for r in dev if r.get("source") != "candidate"]
    test = load_dataset(DATA / "test.jsonl")
    ex_texts: list[str] = []
    ex_labels: list[int] = []
    if not args.no_exemplars:
        for intent, texts in yaml.safe_load(EXEMPLARS.read_text(encoding="utf-8")).items():
            if intent in IDX:
                ex_texts += texts
                ex_labels += [IDX[intent]] * len(texts)
    dev_texts = [model_input(r, args.with_history) for r in dev]
    dev_labels = [IDX[r["intent"]] for r in dev]
    if args.augment_history:
        pool_prev = sorted({r["previous_turn"] for r in dev if r.get("previous_turn")})
        rng = random.Random(args.seed)

        def with_random_prev(text: str) -> str:
            if rng.random() >= 0.5:
                return text
            return f"Previous message: {rng.choice(pool_prev)}\nCurrent message: {text}"

        dev_texts = [t if r.get("previous_turn") else with_random_prev(t) for r, t in zip(dev, dev_texts, strict=True)]
        ex_texts = [with_random_prev(t) for t in ex_texts]

    fold = folds([f"{r['intent']}/{r.get('subtype') or ''}" for r in dev], args.folds, args.seed)
    test_texts = [model_input(r, args.with_history) for r in test]
    if args.modal:
        oof, probs, ms, saved, health = run_modal(args, dev_texts, dev_labels, ex_texts, ex_labels, fold,
                                                  test_texts)
        picked = {d: pick_threshold(dev, oof, deferred) for d, deferred in DESIGNS.items()}
    else:
        oof, picked, probs, ms, saved = run_kaggle(args, base, token, dev, dev_texts, dev_labels, ex_texts,
                                                   ex_labels, fold, test_texts)
    designs = {d: {"min_conf": mc, "dev_oof": dict(ds), "test": dict(score(test, probs, mc, DESIGNS[d])),
                   "test_threshold_sweep": {str(t): dict(score(test, probs, t, DESIGNS[d])) for t in CONF_GRID}}
               for d, (ds, mc) in picked.items()}  # the sweep is diagnostic only, never for selection
    min_conf = picked["flat"][1]
    s = score(test, probs, min_conf)

    per = []
    for row, pr in zip(test, probs, strict=True):
        intent, conf, route = route_of(pr, min_conf)
        per.append({"id": row["id"], "intent": row["intent"], "pred": intent, "conf": round(conf, 4),
                    "route": route, "route_two_group": route_of(pr, picked["two_group"][1], DEFERRED)[2],
                    "proba": [round(float(x), 5) for x in pr]})
    combo = None
    if BASELINE.exists():  # rules + semantic router decide first, SetFit only where they chose RAG
        b = {x["id"]: x["pred"] for x in map(json.loads, BASELINE.read_text(encoding="utf-8").splitlines())}
        combo = Counter()
        for x in per:
            br = EXPECTED.get(b[x["id"]], b[x["id"]])
            route = br if br != RAG else x["route"]
            want = EXPECTED[x["intent"]]
            combo["costly"] += x["intent"] in COSTLY and route != RAG
            combo["routed_ok"] += want != RAG and route == want

    short = args.model.split("/")[-1].lower()
    pool = 'pool187' if args.no_candidates else f'pool{len(dev)}'
    name = args.name or f"setfit-{short}-{pool}{'-hist' if args.with_history else ''}"
    out = EVAL_ROOT / "results" / "routing" / f"{name}-test"
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "oof.npy", oof)  # dev out-of-fold probabilities, for offline calibration
    metrics = {
        "model": args.model, "server": health, "with_history": args.with_history,
        "train_rows": len(dev_texts) + len(ex_texts), "pool_rows": len(dev),
        "pool_sources": dict(Counter(r.get("source", "?") for r in dev)), "exemplar_rows": len(ex_texts),
        "setfit": {"iterations": args.iterations, "epochs": args.epochs, "batch_size": args.batch_size},
        "labels": list(LABELS), "deferred_in_two_group": sorted(DEFERRED), "designs": designs,
        "intent_accuracy": round(s["intent_ok"] / len(test), 3),
        "rules_router_then_setfit": dict(combo) if combo is not None else None,
        "server_ms": _stats(ms), "saved": saved,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "per_question.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in per) + "\n",
                                            encoding="utf-8")
    brief = {d: {k: v for k, v in r.items() if k != "test_threshold_sweep"} for d, r in designs.items()}
    print(json.dumps({"pool_sources": metrics["pool_sources"], "designs": brief,
                      "intent_accuracy": metrics["intent_accuracy"], "server_ms": metrics["server_ms"],
                      "saved": saved}, indent=1))
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
