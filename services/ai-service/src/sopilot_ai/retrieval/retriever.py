"""Retrieval pipeline: branches, fusion, rerank, gate (TECH-V2-ai-service §6.2–§6.4).

Steps for one question, all inside the caller's tenant transaction:

1. dense and/or BM25 candidates (``candidate_pool`` each), access-filtered before ``LIMIT``;
2. ``hybrid``: RRF with the per-language BM25 factor, plus ``doc_code_boost`` for candidates of a
   version whose ``docCode`` is named in the question;
3. the best ``rerank_pool`` candidates; in ``hybrid`` every one gets a ``dense_score`` (direct
   cosine for BM25-only candidates);
4. rerank (if a provider is configured) before the gate, then reorder by ``rerank_score``;
5. gate: the gate score of the best candidate against the threshold of the effective mode.

The four scores are kept apart on every candidate; nothing is rescaled into one "similarity".
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.providers.embedding import EmbeddingProvider
from sopilot_ai.providers.registry import RetrievalConfig
from sopilot_ai.providers.rerank import RerankProvider
from sopilot_ai.qa.doc_code import find_doc_codes, normalize_code
from sopilot_ai.retrieval import fusion, search
from sopilot_ai.retrieval.access_filter import Principal
from sopilot_ai.retrieval.lexical import tokenize


@dataclass
class Candidate:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    lang: str | None = None
    dense_score: float | None = None
    bm25_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    doc_code_match: bool = False
    rank: int = 0  # 1-based, final order


@dataclass
class RetrievalResult:
    mode: str  # dense | bm25 | hybrid | hybrid_rerank (the gate's mode)
    candidates: list[Candidate]
    gate_score: float | None
    threshold: float | None
    passed: bool
    hits: list[Candidate] = field(default_factory=list)  # first context_k when passed
    doc_codes: set[str] = field(default_factory=set)


class Retriever:
    def __init__(self, embedder: EmbeddingProvider, config: RetrievalConfig,
                 reranker: RerankProvider | None = None) -> None:
        self.embedder = embedder
        self.config = config
        self.reranker = reranker
        if reranker is not None and config.mode != "hybrid":
            raise ValueError("rerank runs on hybrid candidates only (mode hybrid_rerank, §6.4)")

    @property
    def mode(self) -> str:
        """Mode of the gate: ``dense``, ``bm25``, ``hybrid`` or ``hybrid_rerank``."""
        return "hybrid_rerank" if self.reranker is not None else self.config.mode

    async def embed_query(self, query: str) -> np.ndarray:
        out = await asyncio.to_thread(self.embedder.embed, [query], is_query=True)
        return out[0]

    async def retrieve(self, conn: AsyncConnection, principal: Principal, query: str, *,
                       query_lang: str | None = None,
                       query_vector: np.ndarray | None = None) -> RetrievalResult:
        cfg = self.config
        base_mode = cfg.mode
        model, revision = self.embedder.model, self.embedder.revision
        qvec = None
        if base_mode in ("dense", "hybrid"):
            qvec = query_vector if query_vector is not None else await self.embed_query(query)

        dense_hits = (await search.dense(conn, principal, qvec, model=model, revision=revision,
                                         pool=cfg.candidate_pool)
                      if qvec is not None else [])
        bm25_hits = (await search.bm25(conn, principal, tokenize(query, role="query"),
                                       pool=cfg.candidate_pool)
                     if base_mode in ("bm25", "hybrid") else [])

        cands: dict[UUID, Candidate] = {}
        for h in dense_hits:
            cands[h.chunk_id] = Candidate(h.chunk_id, h.document_id, h.version_id, h.lang,
                                          dense_score=h.score)
        for h in bm25_hits:
            c = cands.setdefault(h.chunk_id, Candidate(h.chunk_id, h.document_id, h.version_id,
                                                       h.lang))
            c.bm25_score = h.score

        codes: set[str] = set()
        if base_mode == "dense":
            order = [h.chunk_id for h in dense_hits]
        elif base_mode == "bm25":
            order = [h.chunk_id for h in bm25_hits]
        else:
            dense_rank = [h.chunk_id for h in dense_hits]
            bm25_rank = [h.chunk_id for h in bm25_hits]
            item_w = [None, fusion.cross_lingual_weights(
                {h.chunk_id: h.lang for h in bm25_hits}, query_lang,
                cfg.cross_lingual_bm25_factor)]
            fused = fusion.rrf([dense_rank, bm25_rank], cfg.rrf_weights, cfg.rrf_k, item_w)
            codes = find_doc_codes(query)
            if codes and cfg.doc_code_boost:
                versions = list({cands[k].version_id for k in fused})
                version_codes = await search.doc_codes(conn, principal, versions)
                matching = {k for k in fused
                            if normalize_code(version_codes.get(cands[k].version_id, "")) in codes}
                for k in matching:
                    cands[k].doc_code_match = True
                fused = fusion.apply_doc_code_boost(fused, matching, cfg.doc_code_boost)
            for k, score in fused.items():
                cands[k].fusion_score = score
            order = fusion.order(fused, tie_key=str)

        pool = [cands[k] for k in order[:cfg.rerank_pool]]

        if base_mode == "hybrid" and qvec is not None:
            missing = [c.chunk_id for c in pool if c.dense_score is None]
            direct = await search.cosine_by_id(conn, principal, qvec, missing, model=model,
                                               revision=revision)
            for c in pool:
                if c.dense_score is None and c.chunk_id in direct:
                    c.dense_score = direct[c.chunk_id]
            # A chunk with another embedding model has no comparable cosine: drop it rather
            # than gate on a missing score (the startup check reports such versions).
            pool = [c for c in pool if c.dense_score is not None]

        gate_mode = base_mode
        if self.reranker is not None and pool:
            texts = await search.index_texts(conn, principal, [c.chunk_id for c in pool])
            pool = [c for c in pool if c.chunk_id in texts]
            scores = await asyncio.to_thread(self.reranker.score, query,
                                             [texts[c.chunk_id] for c in pool])
            for c, s in zip(pool, scores, strict=True):
                c.rerank_score = float(s)
            pool = [pool[int(j)] for j in np.argsort(-np.asarray(scores), kind="stable")]
            gate_mode = "hybrid_rerank"

        for i, c in enumerate(pool, start=1):
            c.rank = i
        threshold = fusion.threshold_for(gate_mode, cfg.thresholds)
        gate = fusion.gate_score(gate_mode, pool[0]) if pool else None
        passed = bool(pool) and fusion.passes(gate, threshold)
        return RetrievalResult(
            mode=gate_mode, candidates=pool, gate_score=gate, threshold=threshold,
            passed=passed, hits=pool[:cfg.context_k] if passed else [], doc_codes=codes)
