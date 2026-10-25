"""Dense, BM25 and hybrid (RRF) retrieval over an in-memory chunk index, plus optional cross-encoder rerank."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from itertools import pairwise

import numpy as np


def tokenize(text: str) -> list[str]:
    """Vietnamese is syllable-delimited: lowercase unigrams + bigrams, diacritics preserved."""
    toks = re.findall(r"\w+", unicodedata.normalize("NFC", text.lower()))
    return toks + [f"{a}_{b}" for a, b in pairwise(toks)]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=np.float32)
        self.avg = float(self.len.mean()) or 1.0
        df = Counter(t for d in self.tf for t in d)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        s = np.zeros(len(self.tf), dtype=np.float32)
        for t in set(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t)
                if f:
                    s[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return s


class Index:
    def __init__(self, chunks, embedder):
        self.chunks = chunks
        self.embedder = embedder
        self.matrix = embedder.embed([c.text for c in chunks])
        self.bm25 = BM25([tokenize(c.text) for c in chunks])

    def dense(self, query: str) -> np.ndarray:
        return self.matrix @ self.embedder.embed([query], is_query=True)[0]

    def sparse(self, query: str) -> np.ndarray:
        return self.bm25.scores(tokenize(query))


def _rank(scores: np.ndarray) -> list[int]:
    return [int(i) for i in np.argsort(-scores, kind="stable")]


def rrf(rankings: list[list[int]], weights: list[float], k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking, w in zip(rankings, weights):
        for r, idx in enumerate(ranking):
            fused[idx] = fused.get(idx, 0.0) + w / (k + r + 1)
    return fused


class CrossEncoder:
    def __init__(self, model: str, revision: str | None = None):
        from sentence_transformers import CrossEncoder as CE

        self.model = CE(model, revision=revision, max_length=512)

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.predict([(query, t) for t in texts]), dtype=np.float32)


def retrieve(index: Index, query: str, cfg: dict, reranker: CrossEncoder | None, pool: int = 25):
    """Return [(chunk_idx, gate_score)] best-first. gate_score is what a refusal threshold compares against."""
    mode = cfg["retriever"]
    if mode not in {"dense", "bm25", "hybrid"} or pool <= 0:
        raise ValueError("retriever must be dense, bm25 or hybrid, with a positive pool")
    if cfg.get("rerank") and reranker is None:
        raise ValueError("rerank configuration requires a loaded reranker")
    dense = index.dense(query) if mode in ("dense", "hybrid") else None
    sparse = index.sparse(query) if mode in ("bm25", "hybrid") else None
    if mode == "dense":
        ranked = [(i, float(dense[i])) for i in _rank(dense)[:pool]]
    elif mode == "bm25":
        ranked = [(i, float(sparse[i])) for i in _rank(sparse)[:pool]]
    else:
        w = cfg.get("weights", [1.0, 1.0])
        fused = rrf([_rank(dense)[: pool * 2], _rank(sparse)[: pool * 2]], w, cfg.get("rrf_k", 60))
        # Gate on dense cosine (comparable across queries); RRF scores are rank-based, not calibrated.
        ranked = [(i, float(dense[i])) for i in sorted(fused, key=fused.get, reverse=True)[:pool]]
    if cfg.get("rerank") and reranker is not None:
        sc = reranker.score(query, [index.chunks[i].text for i, _ in ranked])
        order = np.argsort(-sc, kind="stable")
        ranked = [(ranked[int(j)][0], float(sc[j])) for j in order]
    return ranked
