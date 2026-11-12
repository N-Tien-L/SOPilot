"""Build the :class:`QAService` from settings and ``config/models.yaml``.

Done on the first question, not at startup: it loads the embedding model and needs the LLM
endpoint, and the API must still start (and serve documents, health and conversation reads)
when either is not set up. A configuration problem surfaces as a ``503`` on the first question
and is logged without any value.
"""
from __future__ import annotations

import asyncio
import hashlib

import numpy as np
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.config import Settings
from sopilot_ai.conversations.service import QAService
from sopilot_ai.db.engine import system_tx
from sopilot_ai.db.repositories import embedding_cache
from sopilot_ai.providers.embedding import EmbeddingProvider, build_embedding_provider
from sopilot_ai.providers.llm import build_chain, check_model
from sopilot_ai.providers.registry import ModelsConfig
from sopilot_ai.providers.rerank import build_rerank_provider
from sopilot_ai.qa import router
from sopilot_ai.quota.counters import QuotaCounter
from sopilot_ai.retrieval.retriever import Retriever

log = structlog.get_logger(__name__)

# Exemplars are embedded as queries; the prefix keeps their cache rows apart from the passage
# vectors of ingest, which are keyed by the same (model, revision, sha256) columns.
EXEMPLAR_CACHE_PREFIX = "router-exemplar-query:"


def exemplar_hash(text: str) -> bytes:
    return hashlib.sha256((EXEMPLAR_CACHE_PREFIX + text).encode("utf-8")).digest()


async def build_router(engine: AsyncEngine, embedder: EmbeddingProvider) -> router.SemanticLayer:
    """The V2-27 layer, its exemplar vectors read from and written to ``rag.embedding_cache``.

    The cache key holds the active model and revision, so a changed embedding model embeds the
    exemplars again; vectors of two models are never compared.
    """
    exemplars = router.load_exemplars()
    model_id = f"{embedder.model}@{embedder.revision}"
    hashes = {t: exemplar_hash(t) for ts in exemplars.values() for t in ts}
    async with system_tx(engine) as conn:
        stored = await embedding_cache.get_many(conn, embedder.model, embedder.revision,
                                                list(set(hashes.values())))
    cache: dict[tuple[str, str], np.ndarray] = {
        (model_id, t): stored[h] for t, h in hashes.items() if h in stored}
    known = set(cache)
    layer = await asyncio.to_thread(
        router.SemanticLayer, embedder, model_id=model_id, exemplars=exemplars,
        thresholds=router.load_thresholds(), cache=cache)
    fresh = [(hashes[t], v) for (_, t), v in cache.items() if (model_id, t) not in known]
    if fresh:
        async with system_tx(engine) as conn:
            await embedding_cache.put_many(conn, embedder.model, embedder.revision, fresh)
    log.info("semantic_router_ready", exemplars=len(hashes), embedded=len(fresh))
    return layer


async def build_service(settings: Settings, engine: AsyncEngine) -> QAService:
    config = ModelsConfig.load(settings.models_config)
    # Chains first: a missing endpoint or model id fails here, before the embedding model loads.
    generate = build_chain(config, "generate")
    rewrite = build_chain(config, "rewrite")
    embedder = await asyncio.to_thread(build_embedding_provider, config, settings.profile)
    reranker = await asyncio.to_thread(build_rerank_provider, config, settings.profile)
    retriever = Retriever(embedder, config.retrieval(), reranker)
    for client in {id(c): c for c in (*generate.clients, *rewrite.clients)}.values():
        await asyncio.to_thread(check_model, client)  # warns, never fails (V2-10)
    semantic = (await build_router(engine, embedder)
                if settings.semantic_router_enabled else None)
    return QAService(
        engine, retriever, generate, rewrite, context=config.context(),
        quota=QuotaCounter(engine, per_user_day=settings.quota_questions_per_user_day,
                           system_day=settings.quota_questions_system_day),
        max_question_chars=settings.max_question_chars,
        followup_max_tokens=settings.followup_max_tokens,
        support_contact=settings.support_contact, timezone=settings.timezone,
        semantic=semantic)
