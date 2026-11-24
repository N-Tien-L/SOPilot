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
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
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


@dataclass(frozen=True)
class AltQuery:
    """The question in the other language (§6.4b): searched next to the original, and used to
    rerank the chunks written in that language."""

    text: str
    lang: str


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


@dataclass(frozen=True)
class RetrievalStats:
    """Candidate counts and phase timings through the retrieval funnel."""

    dense_count: int = 0
    bm25_count: int = 0
    alt_dense_count: int = 0
    alt_bm25_count: int = 0
    fused_count: int = 0
    rerank_pool_count: int = 0
    doc_code_matches: int = 0
    dense_ms: int = 0
    bm25_ms: int = 0
    rrf_ms: int = 0
    rerank_ms: int = 0
    rerank_enabled: bool = False
    rerank_model: str | None = None


PhaseHook = Callable[[str, str, int | None, dict[str, Any] | None], None]


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


@dataclass
class RetrievalResult:
    mode: str  # dense | bm25 | hybrid | hybrid_rerank (the gate's mode)
    candidates: list[Candidate]
    gate_score: float | None
    threshold: float | None
    passed: bool
    hits: list[Candidate] = field(default_factory=list)  # first context_k when passed
    doc_codes: set[str] = field(default_factory=set)
    stats: RetrievalStats = field(default_factory=RetrievalStats)


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
                       query_vector: np.ndarray | None = None,
                       alt: AltQuery | None = None,
                       on_phase: PhaseHook | None = None) -> RetrievalResult:
        def emit_phase(name: str, status: str, ms: int | None = None,
                       detail: dict[str, Any] | None = None) -> None:
            if on_phase is not None:
                on_phase(name, status, ms, detail)

        cfg = self.config
        base_mode = cfg.mode
        model, revision = self.embedder.model, self.embedder.revision

        # Phase 1: Dense Vector Search
        qvec = None
        alt_vec: np.ndarray | None = None
        dense_hits: list[search.Hit] = []
        alt_dense: list[search.Hit] = []
        dense_ms = 0
        if base_mode in ("dense", "hybrid"):
            emit_phase("retrieve_dense", "running")
            t0 = time.monotonic()
            qvec = query_vector if query_vector is not None else await self.embed_query(query)
            dense_hits = await search.dense(conn, principal, qvec, model=model, revision=revision,
                                            pool=cfg.candidate_pool)
            if alt is not None:
                alt_vec = await self.embed_query(alt.text)
                alt_dense = await search.dense(conn, principal, alt_vec, model=model,
                                               revision=revision, pool=cfg.candidate_pool)
            dense_ms = _ms(t0)
            top_dense = max((h.score for h in [*dense_hits, *alt_dense]), default=None)
            emit_phase("retrieve_dense", "passed", dense_ms, {
                "model": model,
                "reusedVector": query_vector is not None,
                "denseCount": len(dense_hits),
                "altDenseCount": len(alt_dense),
                "topScore": round(float(top_dense), 4) if top_dense is not None else None,
            })
        else:
            emit_phase("retrieve_dense", "skipped", 0, {
                "skipped": True, "reason": f"{base_mode}_only_mode",
            })

        # Phase 2: Sparse Lexical Search (BM25)
        bm25_hits: list[search.Hit] = []
        alt_bm25: list[search.Hit] = []
        bm25_ms = 0
        if base_mode in ("bm25", "hybrid"):
            emit_phase("retrieve_sparse", "running")
            t0 = time.monotonic()
            q_terms = tokenize(query, role="query")
            bm25_hits = await search.bm25(conn, principal, q_terms, pool=cfg.candidate_pool)
            if alt is not None:
                alt_bm25 = await search.bm25(conn, principal, tokenize(alt.text, role="query"),
                                             pool=cfg.candidate_pool)
            bm25_ms = _ms(t0)
            top_bm25 = max((h.score for h in [*bm25_hits, *alt_bm25]), default=None)
            emit_phase("retrieve_sparse", "passed", bm25_ms, {
                "bm25Count": len(bm25_hits),
                "altBm25Count": len(alt_bm25),
                "terms": q_terms[:20],
                "termCount": len(q_terms),
                "topScore": round(float(top_bm25), 4) if top_bm25 is not None else None,
            })
        else:
            emit_phase("retrieve_sparse", "skipped", 0, {
                "skipped": True, "reason": f"{base_mode}_only_mode",
            })

        # Phase 3: RRF Fusion & Doc-Code Boost
        t_rrf = time.monotonic()
        if base_mode == "hybrid":
            emit_phase("retrieve_rrf", "running")

        cands: dict[UUID, Candidate] = {}
        for h in [*dense_hits, *alt_dense]:
            c = cands.get(h.chunk_id)
            if c is None:
                cands[h.chunk_id] = Candidate(h.chunk_id, h.document_id, h.version_id, h.lang,
                                              dense_score=h.score)
            elif c.dense_score is None or h.score > c.dense_score:
                c.dense_score = h.score  # the better of the two questions' cosines
        for h in [*bm25_hits, *alt_bm25]:
            c = cands.setdefault(h.chunk_id, Candidate(h.chunk_id, h.document_id, h.version_id,
                                                       h.lang))
            if c.bm25_score is None or h.score > c.bm25_score:
                c.bm25_score = h.score

        codes: set[str] = set()
        if base_mode == "dense":
            order = ([h.chunk_id for h in dense_hits] if alt is None else
                     sorted((k for k, c in cands.items() if c.dense_score is not None),
                            key=lambda k: (-(cands[k].dense_score or 0.0), str(k))))
        elif base_mode == "bm25":
            order = ([h.chunk_id for h in bm25_hits] if alt is None else
                     sorted((k for k, c in cands.items() if c.bm25_score is not None),
                            key=lambda k: (-(cands[k].bm25_score or 0.0), str(k))))
        else:
            dense_rank = [h.chunk_id for h in dense_hits]
            bm25_rank = [h.chunk_id for h in bm25_hits]
            rankings = [dense_rank, bm25_rank]
            weights = list(cfg.rrf_weights)
            item_w = [None, fusion.cross_lingual_weights(
                {h.chunk_id: h.lang for h in bm25_hits}, query_lang,
                cfg.cross_lingual_bm25_factor)]
            if alt is not None:  # the translated question adds its own two lists (§6.4b)
                rankings += [[h.chunk_id for h in alt_dense], [h.chunk_id for h in alt_bm25]]
                weights += list(cfg.rrf_weights)
                item_w += [None, fusion.cross_lingual_weights(
                    {h.chunk_id: h.lang for h in alt_bm25}, alt.lang,
                    cfg.cross_lingual_bm25_factor)]
            fused = fusion.rrf(rankings, weights, cfg.rrf_k, item_w)
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
            if alt_vec is not None:
                for k, v in (await search.cosine_by_id(conn, principal, alt_vec, missing,
                                                       model=model, revision=revision)).items():
                    direct[k] = max(direct.get(k, v), v)
            for c in pool:
                if c.dense_score is None and c.chunk_id in direct:
                    c.dense_score = direct[c.chunk_id]
            # A chunk with another embedding model has no comparable cosine: drop it rather
            # than gate on a missing score (the startup check reports such versions).
            pool = [c for c in pool if c.dense_score is not None]

        rrf_ms = _ms(t_rrf) if base_mode == "hybrid" else 0
        if base_mode == "hybrid":
            emit_phase("retrieve_rrf", "passed", rrf_ms, {
                "denseCount": len(dense_hits) + len(alt_dense),
                "bm25Count": len(bm25_hits) + len(alt_bm25),
                "fusedCount": len(cands),
                "poolCount": len(pool),
                "rrfK": cfg.rrf_k,
                "rrfWeights": list(cfg.rrf_weights),
                "docCodes": sorted(codes),
                "docCodeMatches": sum(1 for c in pool if c.doc_code_match),
                "docCodeBoost": cfg.doc_code_boost,
            })
        else:
            emit_phase("retrieve_rrf", "skipped", 0, {
                "skipped": True, "reason": f"{base_mode}_only_mode",
            })

        # Phase 4: Cross-Encoder Reranker & Gate
        emit_phase("retrieve_rerank", "running")
        t_rerank = time.monotonic()
        gate_mode = base_mode
        if self.reranker is not None and pool:
            texts = await search.index_texts(conn, principal, [c.chunk_id for c in pool])
            pool = [c for c in pool if c.chunk_id in texts]
            # A chunk is scored against the question in its own language (§6.4b): a pair in one
            # language scores far higher than the same pair across two. Without a translation
            # this is one call with the original question, as before.
            groups: dict[str, list[int]] = {}
            for i, c in enumerate(pool):
                q = alt.text if alt is not None and c.lang == alt.lang else query
                groups.setdefault(q, []).append(i)
            scores = np.zeros(len(pool), dtype=np.float32)
            for q, idx in groups.items():
                got = await asyncio.to_thread(self.reranker.score, q,
                                              [texts[pool[i].chunk_id] for i in idx])
                for i, v in zip(idx, got, strict=True):
                    scores[i] = float(v)
            for c, s in zip(pool, scores, strict=True):
                c.rerank_score = float(s)
            pool = [pool[int(j)] for j in np.argsort(-scores, kind="stable")]
            gate_mode = "hybrid_rerank"
        rerank_ms = _ms(t_rerank)

        for i, c in enumerate(pool, start=1):
            c.rank = i
        threshold = fusion.threshold_for(gate_mode, cfg.thresholds)
        gate = fusion.gate_score(gate_mode, pool[0]) if pool else None
        passed = bool(pool) and fusion.passes(gate, threshold)
        rerank_model = getattr(self.reranker, "model", None) if self.reranker is not None else None
        stats = RetrievalStats(
            dense_count=len(dense_hits),
            bm25_count=len(bm25_hits),
            alt_dense_count=len(alt_dense),
            alt_bm25_count=len(alt_bm25),
            fused_count=len(cands),
            rerank_pool_count=len(pool),
            doc_code_matches=sum(1 for c in pool if c.doc_code_match),
            dense_ms=dense_ms,
            bm25_ms=bm25_ms,
            rrf_ms=rrf_ms,
            rerank_ms=rerank_ms,
            rerank_enabled=self.reranker is not None,
            rerank_model=str(rerank_model) if rerank_model else None,
        )
        return RetrievalResult(
            mode=gate_mode, candidates=pool, gate_score=gate, threshold=threshold,
            passed=passed, hits=pool[:cfg.context_k] if passed else [], doc_codes=codes,
            stats=stats)
