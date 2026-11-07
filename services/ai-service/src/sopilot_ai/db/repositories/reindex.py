"""Active versions out of step with the active model or normalizer (TECH-V2-ai-service §5.2)."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class StaleVersion:
    workspace_id: UUID
    document_id: UUID
    version_id: UUID


async def stale_versions(conn: AsyncConnection, *, model: str, revision: str,
                         normalizer_version: str, every: bool = False) -> list[StaleVersion]:
    """Cross-workspace, through ``rag.stale_active_versions`` (call inside ``system_tx``)."""
    rows = (await conn.execute(text(
        "SELECT workspace_id, document_id, version_id "
        "FROM rag.stale_active_versions(:model, :rev, :nv, :all)"),
        {"model": model, "rev": revision, "nv": normalizer_version, "all": every})).all()
    return [StaleVersion(r.workspace_id, r.document_id, r.version_id) for r in rows]


async def requeue_version(conn: AsyncConnection, version_id: UUID) -> bool:
    """Put the finished job of an active version back in the queue, marked ``reindex``.

    A reindex job sends no status callback: the version stays ``READY`` in core-api, and its
    chunks are replaced in the activation transaction (§5.6), so retrieval never sees a gap.
    Returns False when the version has no finished job (for example one already queued).
    """
    row = (await conn.execute(text("""
        UPDATE rag.ingestion_jobs
           SET status = 'QUEUED', attempts = 0, failure_code = NULL, lease_until = NULL,
               run_after = now(), stage_timings = NULL,
               payload = payload || '{"reindex": true}'::jsonb
         WHERE version_id = :ver AND status IN ('DONE', 'FAILED', 'CANCELLED')
        RETURNING id"""), {"ver": version_id})).first()
    if row is not None:
        await conn.execute(text("SELECT pg_notify('rag_jobs', '')"))
    return row is not None
