"""Deliver ``rag.outbox_events`` to core-api (TECH-V2-ai-service §8, TECH-V2-core-api §7, §8.2).

Rules shared with core-api: ``Idempotency-Key`` = event id; backoff ``2^attempts`` s capped at
10 min with jitter; ``DEAD`` after ``SOPILOT_OUTBOX_MAX_ATTEMPTS`` (20); a ``4xx`` other than
``408``/``429`` is a contract error and goes ``DEAD`` at once (this includes ``409`` for an
invalid status transition, which ai-service must not retry).
"""
from __future__ import annotations

import random

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.db.engine import system_tx, tenant_tx
from sopilot_ai.db.repositories import outbox
from sopilot_ai.db.repositories.outbox import OutboxEvent

log = structlog.get_logger(__name__)

_RETRYABLE_4XX = {408, 429}
_MAX_BACKOFF_SECONDS = 600.0


def backoff_seconds(attempts: int) -> float:
    base = min(2.0 ** attempts, _MAX_BACKOFF_SECONDS)
    return base * random.uniform(0.8, 1.2)  # noqa: S311 - jitter, not security


def request_for(event: OutboxEvent) -> tuple[str, str]:
    """HTTP method and path of an event (TECH-V2-core-api §8.2)."""
    if event.event_type == "VERSION_STATUS":
        version_id = event.payload["versionId"]
        return "PATCH", f"/internal/documents/{event.aggregate_id}/versions/{version_id}/status"
    if event.event_type == "SUGGESTIONS_READY":
        return "PUT", f"/internal/documents/{event.aggregate_id}/suggestions"
    raise ValueError(f"unknown outbox event type {event.event_type}")


def body_for(event: OutboxEvent) -> dict:
    """``versionId`` is part of the path for status events, not of the contract body."""
    if event.event_type == "VERSION_STATUS":
        return {k: v for k, v in event.payload.items() if k != "versionId"}
    return dict(event.payload)


class OutboxDispatcher:
    def __init__(self, engine: AsyncEngine, client: httpx.AsyncClient, internal_token: str,
                 max_attempts: int = 20, batch_size: int = 20, lease_seconds: int = 60) -> None:
        self.engine = engine
        self.client = client
        self.token = internal_token
        self.max_attempts = max_attempts
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds

    async def dispatch_due(self) -> int:
        """Send every due event once; returns how many were claimed."""
        total = 0
        while True:
            async with system_tx(self.engine) as conn:
                batch = await outbox.claim_batch(conn, self.batch_size, self.lease_seconds)
            if not batch:
                return total
            total += len(batch)
            for event in batch:
                await self._send(event)

    async def _send(self, event: OutboxEvent) -> None:
        method, path = request_for(event)
        headers = {"X-Internal-Token": self.token, "Idempotency-Key": str(event.id)}
        bound = log.bind(event_id=str(event.id), event_type=event.event_type)
        try:
            resp = await self.client.request(method, path, json=body_for(event), headers=headers)
            status = resp.status_code
            error = f"HTTP {status}"
        except httpx.HTTPError as exc:
            status, error = None, type(exc).__name__
        async with tenant_tx(self.engine, event.workspace_id) as conn:
            if status is not None and 200 <= status < 300:
                await outbox.mark_delivered(conn, event.id)
                return
            attempts = event.attempts + 1
            contract_error = (status is not None and 400 <= status < 500
                              and status not in _RETRYABLE_4XX)
            if contract_error or attempts >= self.max_attempts:
                await outbox.mark_dead(conn, event.id, error)
                bound.error("outbox_event_dead", error=error, attempts=attempts)
                return
            await outbox.mark_retry(conn, event.id, backoff_seconds(attempts), error)
            bound.warning("outbox_delivery_failed", error=error, attempts=attempts)
