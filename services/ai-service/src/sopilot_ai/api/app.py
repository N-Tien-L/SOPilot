"""FastAPI application (``uvicorn sopilot_ai.api.app:create_app --factory``)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.admin import active_embedding, stale_count
from sopilot_ai.api.documents import router as documents_router
from sopilot_ai.api.internal import router as internal_router
from sopilot_ai.auth.jwt import TokenVerifier
from sopilot_ai.config import Settings, get_settings
from sopilot_ai.db.engine import make_engine

log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None, *,
               token_verifier: TokenVerifier | None = None,
               embedding_identity: tuple[str, str] | None = None) -> FastAPI:
    """``embedding_identity`` = active ``(model, revision)``; read from ``models.yaml`` when
    omitted (the model itself is not loaded by the API)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = engine is None
        app.state.engine = engine or make_engine(settings.db_url.get_secret_value())
        try:
            stale = await stale_count(app.state.engine, *app.state.embedding_identity)
            if stale:
                # D2(e): chunks of active versions were embedded by another model or revision
                # (or another normalizer); retrieval skips them until `admin reindex` runs.
                log.error("index_out_of_date", stale_versions=stale,
                          model=app.state.embedding_identity[0],
                          revision=app.state.embedding_identity[1])
            yield
        finally:
            if owned:
                await app.state.engine.dispose()

    app = FastAPI(title="SOPilot ai-service", lifespan=lifespan)
    app.state.internal_token = settings.internal_token.get_secret_value()
    app.state.token_verifier = token_verifier or TokenVerifier(settings.core_jwks_url)
    app.state.embedding_identity = embedding_identity or active_embedding(settings)
    app.include_router(internal_router)
    app.include_router(documents_router)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        stale = await stale_count(app.state.engine, *app.state.embedding_identity)
        if stale:
            return {"status": "degraded", "staleVersions": stale}
        return {"status": "ok"}

    return app
