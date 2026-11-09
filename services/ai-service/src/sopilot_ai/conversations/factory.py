"""Build the :class:`QAService` from settings and ``config/models.yaml``.

Done on the first question, not at startup: it loads the embedding model and needs the LLM
endpoint, and the API must still start (and serve documents, health and conversation reads)
when either is not set up. A configuration problem surfaces as a ``503`` on the first question
and is logged without any value.
"""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.config import Settings
from sopilot_ai.conversations.service import QAService
from sopilot_ai.providers.embedding import build_embedding_provider
from sopilot_ai.providers.llm import build_chain, check_model
from sopilot_ai.providers.registry import ModelsConfig
from sopilot_ai.providers.rerank import build_rerank_provider
from sopilot_ai.quota.counters import QuotaCounter
from sopilot_ai.retrieval.retriever import Retriever

log = structlog.get_logger(__name__)


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
    return QAService(
        engine, retriever, generate, rewrite, context=config.context(),
        quota=QuotaCounter(engine, per_user_day=settings.quota_questions_per_user_day,
                           system_day=settings.quota_questions_system_day),
        max_question_chars=settings.max_question_chars,
        followup_max_tokens=settings.followup_max_tokens,
        support_contact=settings.support_contact, timezone=settings.timezone)
