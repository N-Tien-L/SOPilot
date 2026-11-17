"""Stack a small logistic regression on d1-2B class probabilities (dev CV threshold, one test run).

Run from eval/: PYTHONPATH=. uv run python experiments/routing/stack_d1.py
"""
import json
from pathlib import Path

import numpy as np

from sopilot_eval.routing import EXPECTED, LABELS, RAG
from sopilot_eval.routing_remote import DEFAULT_PHRASES

P2I = {v: k for k, v in DEFAULT_PHRASES.items()}
IDX = {k: i for i, k in enumerate(LABELS)}
def load(split):
    path = Path(f'results/routing/d1-2b-{split}/per_question.jsonl')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    X = np.zeros((len(rows), len(LABELS)))
    for i, r in enumerate(rows):
        for ph, p in r['raw']['intent']['probabilities'].items():
            X[i, IDX[P2I[ph]]] = p
    return rows, np.log(np.clip(X, 1e-6, 1)), np.array([IDX[r['intent']] for r in rows])
def fit(X, y, l2, it=1500, lr=0.1):
    k = len(LABELS); W = np.zeros((X.shape[1], k)); b = np.zeros(k); Y = np.eye(k)[y]
    cnt = np.bincount(y, minlength=k); w = (len(y) / (np.maximum(cnt, 1) * (cnt > 0).sum()))[y]
    for _ in range(it):
        z = X @ W + b; z -= z.max(1, keepdims=True); p = np.exp(z); p /= p.sum(1, keepdims=True)
        g = (p - Y) * w[:, None] / w.sum(); W -= lr * (X.T @ g + l2 * W); b -= lr * g.sum(0)
    return W, b
def proba(m, X):
    z = X @ m[0] + m[1]; z -= z.max(1, keepdims=True); p = np.exp(z); return p / p.sum(1, keepdims=True)
def score(rows, P, mc, dep=frozenset()):
    ok = c = iok = 0
    for r, p in zip(rows, P):
        i = int(p.argmax()); pred = LABELS[i]; route = EXPECTED[pred] if p[i] >= mc else RAG
        if pred in dep: route = RAG
        c += r['intent'] in ('sop_question', 'followup') and route != RAG
        ok += EXPECTED[r['intent']] != RAG and route == EXPECTED[r['intent']]; iok += pred == r['intent']
    return ok, c, iok
drows, Xd, yd = load('dev'); trows, Xt, yt = load('test')
rng = np.random.default_rng(0); fold = np.zeros(len(yd), int)
for c in np.unique(yd):
    ids = rng.permutation(np.where(yd == c)[0]); fold[ids] = np.arange(len(ids)) % 5
for dep, tag in ((frozenset(), '14 labels'), (frozenset({'off_topic', 'legal_medical', 'personal_data'}), 'corpus-dependent -> retrieval')):
    best = None
    for l2 in (1e-3, 1e-2, 1e-1):
        P = np.zeros((len(yd), len(LABELS)))
        for f in range(5):
            P[fold == f] = proba(fit(Xd[fold != f], yd[fold != f], l2), Xd[fold == f])
        for mc in [x / 20 for x in range(20)]:
            ok, c, iok = score(drows, P, mc, dep)
            if c == 0 and (best is None or (ok, iok) > best[0]): best = ((ok, iok), l2, mc)
    _, l2, mc = best
    ok, c, iok = score(trows, proba(fit(Xd, yd, l2), Xt), mc, dep)
    raw_ok, raw_c, raw_iok = score(trows, np.exp(Xt), 0.5, dep)
    print(f'[{tag}] stacked LR (dev CV, l2={l2}, min_conf={mc}): test routed_ok={ok} costly={c} acc={iok/len(trows):.3f}'
          f' | raw d1 @0.5: routed_ok={raw_ok} costly={raw_c}')
