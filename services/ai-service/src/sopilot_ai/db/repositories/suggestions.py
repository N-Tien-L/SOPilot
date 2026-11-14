"""``rag.suggestion_jobs``, ``rag.suggestion_cache`` and the extracted text they read (V2-25).

``claim`` crosses workspaces through ``rag.claim_suggestion_job`` (call inside ``system_tx``); every
other statement runs in ``tenant_tx`` and filters ``workspace_id`` next to RLS.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class ClaimedSuggestion:
    id: UUID
    workspace_id: UUID
    document_id: UUID
    version_id: UUID
    input: dict[str, Any]
    attempts: int


@dataclass(frozen=True)
class ExtractedText:
    markdown: str
    language: str | None


_ENQUEUE = text("""
INSERT INTO rag.suggestion_jobs (id, workspace_id, document_id, version_id, input)
VALUES (:id, :wid, :doc, :ver, CAST(:input AS jsonb))
ON CONFLICT (version_id) DO NOTHING
""")
_CLAIM = text("SELECT * FROM rag.claim_suggestion_job(:lease)")
_EXTRACTED = text("""
SELECT markdown, language FROM rag.extracted_documents
 WHERE workspace_id = :wid AND version_id = :ver
""")
_CACHE_GET = text("""
SELECT result FROM rag.suggestion_cache
 WHERE workspace_id = :wid AND cache_key = :key
""")
_CACHE_PUT = text("""
INSERT INTO rag.suggestion_cache (workspace_id, cache_key, result)
VALUES (:wid, :key, CAST(:result AS jsonb))
ON CONFLICT (workspace_id, cache_key) DO NOTHING
""")
# Fenced on ``attempts``: every claim increments it, so a worker whose lease expired and was
# reclaimed no longer matches and cannot finish the job (or emit a second SUGGESTIONS_READY).
_FINISH = text("""
UPDATE rag.suggestion_jobs
   SET status = :status, result = CAST(:result AS jsonb), method = :method,
       timings = CAST(:timings AS jsonb), lease_until = NULL
 WHERE id = :id AND workspace_id = :wid AND status = 'RUNNING' AND attempts = :attempts
""")


def _json(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, default=str)


async def enqueue(conn: AsyncConnection, *, workspace_id: UUID, document_id: UUID,
                  version_id: UUID, input: dict[str, Any]) -> None:
    """One job per version. Called in the same transaction that makes the version READY."""
    await conn.execute(_ENQUEUE, {"id": uuid4(), "wid": workspace_id, "doc": document_id,
                                  "ver": version_id, "input": _json(input)})


async def claim(conn: AsyncConnection, lease_seconds: int) -> ClaimedSuggestion | None:
    row = (await conn.execute(_CLAIM, {"lease": lease_seconds})).mappings().first()
    if row is None:
        return None
    return ClaimedSuggestion(**dict(row))


async def extracted_text(conn: AsyncConnection, workspace_id: UUID,
                         version_id: UUID) -> ExtractedText | None:
    row = (await conn.execute(_EXTRACTED, {"wid": workspace_id, "ver": version_id})).first()
    return None if row is None else ExtractedText(row.markdown, row.language)


async def cache_get(conn: AsyncConnection, workspace_id: UUID, key: bytes) -> dict | None:
    row = (await conn.execute(_CACHE_GET, {"wid": workspace_id, "key": key})).first()
    return None if row is None else row.result


async def cache_put(conn: AsyncConnection, workspace_id: UUID, key: bytes, result: dict) -> None:
    await conn.execute(_CACHE_PUT, {"wid": workspace_id, "key": key, "result": _json(result)})


async def finish(conn: AsyncConnection, job: ClaimedSuggestion, *, status: str,
                 result: dict | None, method: str | None, timings: dict[str, Any]) -> bool:
    """Record the outcome. False when this worker no longer holds the lease (job reclaimed)."""
    res = await conn.execute(_FINISH, {"id": job.id, "wid": job.workspace_id, "status": status,
                                       "result": _json(result), "method": method,
                                       "timings": _json(timings), "attempts": job.attempts})
    return res.rowcount == 1

