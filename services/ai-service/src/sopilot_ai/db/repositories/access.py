"""``rag.document_access`` (ADR-007 §4.5, TECH-V2-ai-service §3.1, §8)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_UPSERT = text("""
INSERT INTO rag.document_access (workspace_id, document_id, visibility, department_ids,
                                 access_revision, title)
VALUES (:wid, :doc, :visibility, CAST(:depts AS uuid[]), :rev, :title)
ON CONFLICT (document_id) DO UPDATE
   SET visibility = EXCLUDED.visibility,
       department_ids = EXCLUDED.department_ids,
       access_revision = EXCLUDED.access_revision
 WHERE rag.document_access.access_revision < EXCLUDED.access_revision
   AND rag.document_access.workspace_id = EXCLUDED.workspace_id
RETURNING document_id
""")


async def upsert_access(conn: AsyncConnection, *, workspace_id: UUID, document_id: UUID,
                        visibility: str, department_ids: list[UUID], access_revision: int,
                        title: str) -> bool:
    """Insert, or apply only when ``access_revision`` is newer. Returns whether it applied.

    ``title`` is written on insert only; activation sets the title of the version it activates.
    """
    row = (await conn.execute(_UPSERT, {
        "wid": workspace_id, "doc": document_id, "visibility": visibility,
        "depts": [str(d) for d in department_ids], "rev": access_revision, "title": title,
    })).first()
    return row is not None


_UPDATE = text("""
UPDATE rag.document_access
   SET visibility = :visibility, department_ids = CAST(:depts AS uuid[]), access_revision = :rev
 WHERE workspace_id = :wid AND document_id = :doc AND deleted_at IS NULL
   AND access_revision < :rev
RETURNING document_id
""")


async def update_access(conn: AsyncConnection, *, workspace_id: UUID, document_id: UUID,
                        visibility: str, department_ids: list[UUID],
                        access_revision: int) -> bool:
    """``PUT /internal/document-access`` (§8): apply only a newer ``access_revision``.

    Chunks are not touched (FR-26: a scope change does not embed again). A document ai-service
    has never seen is not created here: its first ``POST /internal/ingestions`` carries the
    access, so ``applied`` is false.
    """
    row = (await conn.execute(_UPDATE, {
        "wid": workspace_id, "doc": document_id, "visibility": visibility,
        "depts": [str(d) for d in department_ids], "rev": access_revision,
    })).first()
    return row is not None


async def delete_document(conn: AsyncConnection, *, workspace_id: UUID, document_id: UUID) -> None:
    """``DELETE /internal/documents`` (§8), every version, in one transaction.

    ``deleted_at`` is set first, so a concurrent retrieval or activation that already holds the
    row sees the document as gone; then jobs, chunks (terms cascade), extraction results and
    suggestion jobs are removed, and finally the access row. ``message_citations`` stay, so
    history can show ``DOCUMENT_DELETED``. Idempotent: nothing left is not an error.
    """
    p = {"wid": workspace_id, "doc": document_id}
    await conn.execute(text(
        "UPDATE rag.document_access SET deleted_at = now() "
        "WHERE workspace_id = :wid AND document_id = :doc AND deleted_at IS NULL"), p)
    for table in ("ingestion_jobs", "chunks", "extracted_documents", "suggestion_jobs",
                  "document_access"):
        await conn.execute(text(
            f"DELETE FROM rag.{table} WHERE workspace_id = :wid AND document_id = :doc"), p)  # noqa: S608 - constant table names
