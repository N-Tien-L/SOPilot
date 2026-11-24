"""``rag.ingestion_jobs`` (TECH-V2-ai-service §3.2, §5.1, §8)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class ClaimedJob:
    id: UUID
    workspace_id: UUID
    document_id: UUID
    version_id: UUID
    request_attempt: int
    payload: dict[str, Any]
    attempts: int
    failure_code: str | None


# Insert, or put a FAILED job back in the queue when core-api retries with a larger attempt.
# Same attempt, or a QUEUED/RUNNING/DONE/CANCELLED job: untouched (no row returned).
_ENQUEUE = text("""
INSERT INTO rag.ingestion_jobs (id, workspace_id, document_id, version_id, request_attempt, payload)
VALUES (:id, :wid, :doc, :ver, :attempt, CAST(:payload AS jsonb))
ON CONFLICT (version_id) DO UPDATE
   SET status = 'QUEUED', attempts = 0, failure_code = NULL, lease_until = NULL,
       run_after = now(), stage_timings = NULL,
       request_attempt = EXCLUDED.request_attempt, payload = EXCLUDED.payload
 WHERE rag.ingestion_jobs.status = 'FAILED'
   AND EXCLUDED.request_attempt > rag.ingestion_jobs.request_attempt
RETURNING id
""")


async def enqueue(conn: AsyncConnection, *, workspace_id: UUID, document_id: UUID,
                  version_id: UUID, request_attempt: int, payload: dict[str, Any]) -> bool:
    """Returns whether a job was created or re-queued; wakes the worker if so."""
    row = (await conn.execute(_ENQUEUE, {
        "id": uuid4(), "wid": workspace_id, "doc": document_id, "ver": version_id,
        "attempt": request_attempt, "payload": json.dumps(payload, ensure_ascii=False),
    })).first()
    if row is not None:
        await conn.execute(text("SELECT pg_notify('rag_jobs', '')"))
    return row is not None


async def claim(conn: AsyncConnection, lease_seconds: int) -> ClaimedJob | None:
    """Cross-workspace claim through ``rag.claim_ingestion_job`` (call inside ``system_tx``)."""
    row = (await conn.execute(text("SELECT * FROM rag.claim_ingestion_job(:lease)"),
                              {"lease": lease_seconds})).mappings().first()
    if row is None:
        return None
    return ClaimedJob(**dict(row))


def _timings(timings: dict[str, Any] | None) -> str | None:
    return json.dumps(timings) if timings is not None else None


async def requeue(conn: AsyncConnection, job_id: UUID, failure_code: str | None,
                  delay_seconds: float, timings: dict[str, Any] | None) -> None:
    """Transient failure: back to QUEUED with ``run_after`` backoff, no callback (§5.1)."""
    await conn.execute(text("""
        UPDATE rag.ingestion_jobs
           SET status = 'QUEUED', lease_until = NULL, failure_code = :code,
               run_after = now() + make_interval(secs => :delay),
               stage_timings = CAST(:timings AS jsonb)
         WHERE id = :id"""),
        {"id": job_id, "code": failure_code, "delay": delay_seconds, "timings": _timings(timings)})


async def finish(conn: AsyncConnection, job_id: UUID, status: str, failure_code: str | None,
                 timings: dict[str, Any] | None) -> None:
    await conn.execute(text("""
        UPDATE rag.ingestion_jobs
           SET status = :status, lease_until = NULL, failure_code = :code,
               stage_timings = CAST(:timings AS jsonb)
         WHERE id = :id"""),
        {"id": job_id, "status": status, "code": failure_code, "timings": _timings(timings)})


async def newer_version_done(conn: AsyncConnection, document_id: UUID, version_no: int) -> bool:
    """A later version of the document is already active; activating this one would roll back."""
    row = (await conn.execute(text("""
        SELECT 1 FROM rag.ingestion_jobs
         WHERE document_id = :doc AND status = 'DONE'
           AND (payload->>'versionNo')::int > :no
         LIMIT 1"""), {"doc": document_id, "no": version_no})).first()
    return row is not None
