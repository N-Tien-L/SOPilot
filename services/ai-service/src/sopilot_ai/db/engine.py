"""Async engine and tenant-scoped transactions (TECH-V2-ai-service §4.1).

Every transaction that touches a table with ``workspace_id`` starts with
``set_config('app.workspace_id', :wid, true)`` (transaction-local), so a pooled connection never
carries the previous tenant. ``system_tx`` is only for the SECURITY DEFINER helpers and the
tables without RLS (``embedding_cache``, ``processed_requests``, ``system_usage``); it clears
the tenant explicitly.
"""
from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_SET_TENANT = text(
    "SELECT set_config('app.workspace_id', :wid, true), set_config('app.user_id', :uid, true)")


def ensure_selector_loop_policy() -> None:
    """psycopg's async driver cannot run on Windows' default Proactor event loop."""
    if sys.platform == "win32":
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]


def sqlalchemy_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str, pool_size: int = 5) -> AsyncEngine:
    return create_async_engine(sqlalchemy_url(url), pool_size=pool_size, pool_pre_ping=True)


@asynccontextmanager
async def tenant_tx(engine: AsyncEngine, workspace_id: UUID,
                    user_id: UUID | None = None) -> AsyncIterator[AsyncConnection]:
    async with engine.begin() as conn:
        await conn.execute(_SET_TENANT, {"wid": str(workspace_id), "uid": str(user_id or "")})
        yield conn


@asynccontextmanager
async def system_tx(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.begin() as conn:
        await conn.execute(_SET_TENANT, {"wid": "", "uid": ""})
        yield conn


def vector_literal(vec: np.ndarray) -> str:
    """pgvector text input, bound as a parameter and cast with ``CAST(:v AS vector)``."""
    return "[" + ",".join(f"{x:.8g}" for x in np.asarray(vec, dtype=np.float32).tolist()) + "]"


def parse_vector(value: str) -> np.ndarray:
    return np.array([float(x) for x in value.strip("[]").split(",")], dtype=np.float32)
