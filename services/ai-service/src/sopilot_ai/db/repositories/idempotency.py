"""``rag.processed_requests``: Idempotency-Key of ``/internal/**`` (TECH-V2-ai-service §8)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def claim_key(conn: AsyncConnection, key: UUID) -> bool:
    """Record ``key`` in the caller's transaction. False when it was already processed.

    The row commits or rolls back with the change it guards, so a failed request can be resent.
    """
    row = (await conn.execute(text(
        "INSERT INTO rag.processed_requests (idempotency_key) VALUES (:k) "
        "ON CONFLICT DO NOTHING RETURNING idempotency_key"), {"k": key})).first()
    return row is not None
