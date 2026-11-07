"""``rag.outbox_events`` (TECH-V2-ai-service §3.5, §8; rules of TECH-V2-core-api §7)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class OutboxEvent:
    id: UUID
    workspace_id: UUID
    aggregate_id: UUID
    event_type: str
    payload: dict[str, Any]
    attempts: int


async def add(conn: AsyncConnection, *, workspace_id: UUID, aggregate_id: UUID, event_type: str,
              payload: dict[str, Any]) -> UUID:
    event_id = uuid4()
    await conn.execute(text("""
        INSERT INTO rag.outbox_events (id, workspace_id, aggregate_id, event_type, payload)
        VALUES (:id, :wid, :agg, :type, CAST(:payload AS jsonb))"""),
        {"id": event_id, "wid": workspace_id, "agg": aggregate_id, "type": event_type,
         "payload": json.dumps(payload, ensure_ascii=False)})
    return event_id


async def claim_batch(conn: AsyncConnection, limit: int, lease_seconds: int) -> list[OutboxEvent]:
    """Cross-workspace claim through ``rag.claim_outbox_batch`` (call inside ``system_tx``)."""
    rows = await conn.execute(text("SELECT * FROM rag.claim_outbox_batch(:n, :lease)"),
                              {"n": limit, "lease": lease_seconds})
    return [OutboxEvent(**dict(r)) for r in rows.mappings()]


async def mark_delivered(conn: AsyncConnection, event_id: UUID) -> None:
    await conn.execute(text(
        "UPDATE rag.outbox_events SET status = 'DELIVERED', delivered_at = now(), "
        "attempts = attempts + 1, last_error = NULL WHERE id = :id"), {"id": event_id})


async def mark_retry(conn: AsyncConnection, event_id: UUID, delay_seconds: float,
                     error: str) -> None:
    await conn.execute(text(
        "UPDATE rag.outbox_events SET attempts = attempts + 1, last_error = :err, "
        "next_attempt_at = now() + make_interval(secs => :delay) WHERE id = :id"),
        {"id": event_id, "delay": delay_seconds, "err": error[:500]})


async def mark_dead(conn: AsyncConnection, event_id: UUID, error: str) -> None:
    await conn.execute(text(
        "UPDATE rag.outbox_events SET status = 'DEAD', attempts = attempts + 1, last_error = :err "
        "WHERE id = :id"), {"id": event_id, "err": error[:500]})
