"""bge-m3 vectors (same embedder as the service) + softmax logistic regression trained on dev only.

Threshold chosen on dev with 5-fold out-of-fold probabilities (zero costly), then one test run.
Run from eval/: PYTHONPATH=. uv run --extra local python experiments/routing/bge_m3_lr.py <out_dir> [extra_train.jsonl]
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import yaml
from sopilot_ai.providers.embedding import LocalEmbeddingProvider
from sopilot_ai.providers.registry import ModelsConfig

from sopilot_eval.routing import EXPECTED, LABELS, RAG, REPO_ROOT, load_dataset
from sopilot_eval.routing_remote import model_input

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
CONF_GRID = [round(x * 0.05, 2) for x in range(20)]
L2_GRID = [1e-4, 1e-3, 1e-2, 1e-1]

cfg = yaml.safe_load((REPO_ROOT / "eval/configs/routing-rules-router.yaml").read_text(encoding="utf-8"))
spec = ModelsConfig.load(REPO_ROOT / cfg["embedder"]["models_config"]).embedding()
emb = LocalEmbeddingProvider(spec, str(cfg["embedder"]["revision"]))
emb.embed(["khởi động"], is_query=True)

dev = load_dataset(REPO_ROOT / "eval/datasets/routing/dev.jsonl")
if len(sys.argv) > 2:
    dev += load_dataset(REPO_ROOT / sys.argv[2])
test = load_dataset(REPO_ROOT / "eval/datasets/routing/test.jsonl")
ex = yaml.safe_load((REPO_ROOT / "services/ai-service/src/sopilot_ai/qa/router_exemplars.yaml").read_text(encoding="utf-8"))
ex_rows = [(t, k) for k, v in ex.items() if k in LABELS for t in (v if isinstance(v, list) else v.get("examples", []))]
IDX = {k: i for i, k in enumerate(LABELS)}


def vecs(texts):
    return np.asarray(emb.embed(texts, is_query=True), dtype=np.float32)


def fit(X, y, l2, iters=600, lr=2.0):
    n, d = X.shape
    k = len(LABELS)
    cnt = np.bincount(y, minlength=k).astype(np.float32)
    w_cls = np.where(cnt > 0, n / (np.maximum(cnt, 1) * (cnt > 0).sum()), 0.0)
    sw = w_cls[y]
    W = np.zeros((d, k), np.float32)
    b = np.zeros(k, np.float32)
    Y = np.eye(k, dtype=np.float32)[y]
    Xs = X * 10.0  # unit vectors: scale so the logits can move
    for _ in range(iters):
        z = Xs @ W + b
        z -= z.max(1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(1, keepdims=True)
        g = (p - Y) * sw[:, None] / sw.sum()
        W -= lr * (Xs.T @ g + l2 * W)
        b -= lr * g.sum(0)
    return W, b


def proba(model, X):
    W, b = model
    z = (X * 10.0) @ W + b
    z -= z.max(1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(1, keepdims=True)


def decide(p, mc):
    i = int(p.argmax())
    intent, conf = LABELS[i], float(p[i])
    route = EXPECTED[intent]
    if route != RAG and conf < mc:
        route = RAG
    return intent, conf, route


def score(rows, P, mc):
    ok = intent_ok = costly = sop_bad = 0
    for r, p in zip(rows, P, strict=True):
        intent, _, route = decide(p, mc)
        want = EXPECTED[r["intent"]]
        if r["intent"] in ("sop_question", "followup") and route != RAG:
            costly += 1
            sop_bad += r["intent"] == "sop_question"
        ok += want != RAG and route == want
        intent_ok += intent == r["intent"]
    return ok, intent_ok, costly, sop_bad


def oof(X, y, l2, extra=None, folds=5, seed=0):
    rng = np.random.default_rng(seed)
    fold = np.zeros(len(y), int)
    for c in np.unique(y):
        ids = rng.permutation(np.where(y == c)[0])
        fold[ids] = np.arange(len(ids)) % folds
    P = np.zeros((len(y), len(LABELS)))
    for f in range(folds):
        tr = fold != f
        Xt, yt = X[tr], y[tr]
        if extra is not None:
            Xt, yt = np.vstack([Xt, extra[0]]), np.concatenate([yt, extra[1]])
        P[~tr] = proba(fit(Xt, yt, l2), X[~tr])
    return P


summary = {}
for hist in (False, True):
    Xd = vecs([model_input(r, hist) for r in dev])
    t0 = time.perf_counter()
    test_texts = [model_input(r, hist) for r in test]
    lat = []
    Xt_list = []
    for t in test_texts:  # per-question CPU latency, as the service would embed
        s = time.perf_counter()
        Xt_list.append(vecs([t])[0])
        lat.append((time.perf_counter() - s) * 1000)
    Xt = np.vstack(Xt_list)
    yd = np.array([IDX[r["intent"]] for r in dev])
    Xe = vecs([t for t, _ in ex_rows])
    ye = np.array([IDX[k] for _, k in ex_rows])
    for use_ex in (False, True):
        extra = (Xe, ye) if use_ex else None
        best = None
        for l2 in L2_GRID:
            P = oof(Xd, yd, l2, extra)
            for mc in CONF_GRID:
                ok, iok, costly, _ = score(dev, P, mc)
                if costly == 0 and (best is None or (ok, iok) > best[0]):
                    best = ((ok, iok), l2, mc)
        (dev_ok, dev_iok), l2, mc = best
        Xtr, ytr = (np.vstack([Xd, Xe]), np.concatenate([yd, ye])) if use_ex else (Xd, yd)
        model = fit(Xtr, ytr, l2)
        Pt = proba(model, Xt)
        ok, iok, costly, sop_bad = score(test, Pt, mc)
        name = f"lr{'-ex' if use_ex else ''}{'-hist' if hist else ''}"
        per = []
        for r, p in zip(test, Pt, strict=True):
            intent, conf, route = decide(p, mc)
            per.append({"id": r["id"], "intent": r["intent"], "pred": intent, "conf": round(conf, 4), "route": route})
        (OUT / f"{name}.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in per), encoding="utf-8")
        rec = Counter()
        tot = Counter(r["intent"] for r in test)
        for x in per:
            want = EXPECTED[x["intent"]]
            rec[x["intent"]] += (x["route"] == want) if want != RAG else (x["route"] == RAG)
        summary[name] = {"l2": l2, "min_conf": mc, "dev_oof_routed_ok": dev_ok,
                         "test_routed_ok": ok, "non_rag": sum(EXPECTED[r["intent"]] != RAG for r in test),
                         "test_intent_acc": round(iok / len(test), 3), "costly": costly, "sop_misroute": sop_bad,
                         "embed_ms_p50": round(statistics.median(lat), 1),
                         "embed_ms_p95": round(statistics.quantiles(lat, n=20)[18], 1),
                         "route_recall": {k: f"{rec[k]}/{tot[k]}" for k in LABELS}}
        print(name, json.dumps({k: v for k, v in summary[name].items() if k != "route_recall"}), flush=True)
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
