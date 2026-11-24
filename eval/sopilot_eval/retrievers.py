"""Dense, BM25 and hybrid (RRF) retrieval over an in-memory chunk index, plus optional cross-encoder rerank.

The tokenizer, BM25 and fusion are imported from ``sopilot_ai.retrieval`` (V2-09,
TECH-V2-ai-service §6.5), so the harness and ai-service rank with the same code; this module only
keeps the in-memory index and the candidate assembly.
"""
from __future__ import annotations

import numpy as np
from sopilot_ai.retrieval.fusion import cross_lingual_weights as _cross_lingual_weights
from sopilot_ai.retrieval.fusion import gate_score, rrf
from sopilot_ai.retrieval.lexical import (
    BM25,
    FOLD_PREFIX,
    TOKENIZER_VERSION,
    base_terms,
    fold,
    lexical_len,
    tokenize,
)

__all__ = ["BM25", "FOLD_PREFIX", "TOKENIZER_VERSION", "CrossEncoder", "Index", "base_terms",
           "chunk_text", "cross_lingual_weights", "fold", "gate_score", "lexical_len",
           "retrieve", "retrieve_candidates", "rrf", "tokenize"]


def chunk_text(chunk) -> str:
    """What is embedded and indexed: ``index_text`` for docproc chunks, else the raw window."""
    return getattr(chunk, "index_text", None) or chunk.text


class Index:
    def __init__(self, chunks, embedder):
        self.chunks = chunks
        self.embedder = embedder
        texts = [chunk_text(c) for c in chunks]
        self.matrix = embedder.embed(texts)
        self.bm25 = BM25([tokenize(t) for t in texts], lengths=[lexical_len(t) for t in texts])

    def dense(self, query: str) -> np.ndarray:
        return self.matrix @ self.embedder.embed([query], is_query=True)[0]

    def sparse(self, query: str) -> np.ndarray:
        return self.bm25.scores(tokenize(query, role="query"))


def _rank(scores: np.ndarray) -> list[int]:
    return [int(i) for i in np.argsort(-scores, kind="stable")]


def cross_lingual_weights(chunks, ranking: list[int], query_lang: str | None, factor: float) -> dict[int, float]:
    """BM25-branch factor per chunk (TECH-V2-ai-service §6.4), from ``chunks[i].lang``."""
    return _cross_lingual_weights({i: getattr(chunks[i], "lang", None) for i in ranking}, query_lang, factor)


class CrossEncoder:
    def __init__(self, model: str, revision: str | None = None):
        from sentence_transformers import CrossEncoder as CE

        self.model = CE(model, revision=revision, max_length=512)

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        raw = np.asarray(self.model.predict([(query, t) for t in texts], activation_fn=_identity), dtype=np.float32)
        return 1.0 / (1.0 + np.exp(-raw))  # sigmoid explicitly, independent of library defaults


def _identity(x):
    return x


class RemoteCrossEncoder:
    """Same scores as ``CrossEncoder`` but computed on the Modal GPU (V2-35).

    Delegates to ``sopilot_ai.providers.rerank.RemoteRerankProvider`` so harness and service share
    one client. URL and key come from ``SOPILOT_RERANK_BASE_URL`` / ``SOPILOT_LLM_API_KEY``.
    """

    def __init__(self, model: str, revision: str | None = None, timeout_s: float = 600.0):
        import os

        from sopilot_ai.providers.registry import RerankSpec
        from sopilot_ai.providers.rerank import RemoteRerankProvider

        base_url = os.environ.get("SOPILOT_RERANK_BASE_URL", "")
        if not base_url:
            raise SystemExit("rerank provider modal needs SOPILOT_RERANK_BASE_URL (and SOPILOT_LLM_API_KEY)")
        spec = RerankSpec(enabled=True, provider="modal", model=model, revision=revision or "",
                          max_pairs=25, timeout_s=timeout_s)
        self.model = model
        self._provider = RemoteRerankProvider(
            spec, base_url=base_url, api_key=os.environ.get("SOPILOT_LLM_API_KEY") or None,
            timeout=timeout_s)

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        return self._provider.score(query, texts)


def build_reranker(conf: dict):
    """``rerank`` config block -> reranker; ``provider`` is ``local`` (default) or ``modal``."""
    provider = conf.get("provider", "local")
    if provider == "modal":
        return RemoteCrossEncoder(conf["model"], conf.get("revision"), float(conf.get("timeout_s", 600)))
    if provider != "local":
        raise ValueError(f"unknown rerank provider {provider!r}")
    return CrossEncoder(conf["model"], conf.get("revision"))


def retrieve_candidates(index: Index, query: str, cfg: dict, reranker: CrossEncoder | None,
                        pool: int = 25, query_lang: str | None = None) -> list[dict]:
    """Best-first candidates ``{idx, dense_score, bm25_score, fusion_score, rerank_score, gate}``.

    ``dense_score`` is the cosine to every chunk (the in-memory index scores the whole corpus), so a
    hybrid candidate that only the BM25 branch found still has it, as §6.4 requires.
    """
    mode = cfg["retriever"]
    if mode not in {"dense", "bm25", "hybrid"} or pool <= 0:
        raise ValueError("retriever must be dense, bm25 or hybrid, with a positive pool")
    if cfg.get("rerank") and reranker is None:
        raise ValueError("rerank configuration requires a loaded reranker")
    dense = index.dense(query) if mode in ("dense", "hybrid") else None
    sparse = index.sparse(query) if mode in ("bm25", "hybrid") else None
    fusion = None
    if mode == "dense":
        order = _rank(dense)[:pool]
    elif mode == "bm25":
        order = _rank(sparse)[:pool]
    else:
        w = cfg.get("weights", [1.0, 1.0])
        sparse_rank = _rank(sparse)[: pool * 2]
        factor = float(cfg.get("cross_lingual_bm25_factor", 1.0))
        chunks = getattr(index, "chunks", None)
        item_w = [None, cross_lingual_weights(chunks, sparse_rank, query_lang, factor)] if chunks else None
        fusion = rrf([_rank(dense)[: pool * 2], sparse_rank], w, cfg.get("rrf_k", 60), item_w)
        order = sorted(fusion, key=lambda i: (-fusion[i], i))[:pool]
    cands = [
        {
            "idx": i,
            "dense_score": float(dense[i]) if dense is not None else None,
            "bm25_score": float(sparse[i]) if sparse is not None else None,
            "fusion_score": float(fusion[i]) if fusion is not None else None,
            "rerank_score": None,
        }
        for i in order
    ]
    gate_mode = mode
    if cfg.get("rerank") and reranker is not None:
        sc = reranker.score(query, [chunk_text(index.chunks[c["idx"]]) for c in cands])
        for c, s in zip(cands, sc):
            c["rerank_score"] = float(s)
        cands = [cands[int(j)] for j in np.argsort(-sc, kind="stable")]
        gate_mode = "hybrid_rerank"
    for c in cands:
        c["gate"] = gate_score(gate_mode, c)
    return cands


def retrieve(index: Index, query: str, cfg: dict, reranker: CrossEncoder | None, pool: int = 25,
             query_lang: str | None = None):
    """Return [(chunk_idx, gate_score)] best-first. gate_score is what a refusal threshold compares against."""
    return [(c["idx"], c["gate"]) for c in retrieve_candidates(index, query, cfg, reranker, pool, query_lang)]
