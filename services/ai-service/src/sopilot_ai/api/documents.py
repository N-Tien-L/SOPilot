"""Public document content for the citation viewer and FR-31 (TECH-V2-ai-service §7.3)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.auth.jwt import current_principal
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.retrieval.access_filter import Principal, access_params, allowed_cte

router = APIRouter(prefix="/ai/v1", tags=["documents"])

MAX_REMOVED_BLOCKS = 200

# Only the active version of a document the asker may read; anything else is one 404, so
# "missing", "not allowed", "not READY yet", "FAILED" and "deleted" look the same (FR-25).
_CONTENT = text(f"""
WITH {allowed_cte()}
SELECT e.document_id, e.version_id, e.structure->>'file_type' AS file_type,
       e.normalizer_version, e.markdown, e.page_index, e.warnings, e.boilerplate
  FROM rag.extracted_documents e
  JOIN allowed a ON a.document_id = e.document_id AND a.active_version_id = e.version_id
 WHERE e.workspace_id = :wid AND e.document_id = :doc AND e.version_id = :ver
""")


def utf16_offsets(text_: str, indices: Sequence[int]) -> dict[int, int]:
    """Code-point indices to UTF-16 code-unit indices in one pass (browser string offsets)."""
    wanted = sorted(set(indices))
    out: dict[int, int] = {}
    units = 0
    pos = 0
    for idx in wanted:
        for ch in text_[pos:idx]:
            units += 2 if ord(ch) > 0xFFFF else 1
        pos = idx
        out[idx] = units
    return out


def content_response(row: Any) -> dict[str, Any]:
    markdown: str = row.markdown
    pages = row.page_index or []
    offsets = utf16_offsets(markdown, [p[k] for p in pages for k in ("charStart", "charEnd")])
    return {
        "documentId": str(row.document_id),
        "versionId": str(row.version_id),
        "fileType": row.file_type,
        "normalizerVersion": row.normalizer_version,
        "markdown": markdown,
        "pages": [{"page": p["page"], "charStart": p["charStart"], "charEnd": p["charEnd"],
                   "charStart16": offsets[p["charStart"]], "charEnd16": offsets[p["charEnd"]]}
                  for p in pages],
        "warnings": row.warnings or [],
        "removedBlocks": [{"kind": b.get("kind"), "page": b.get("page"), "text": b.get("text")}
                          for b in (row.boilerplate or [])[:MAX_REMOVED_BLOCKS]],
    }


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


@router.get("/documents/{document_id}/versions/{version_id}/content")
async def document_content(
    document_id: UUID,
    version_id: UUID,
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> dict[str, Any]:
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        row = (await conn.execute(_CONTENT, {**access_params(principal), "doc": document_id,
                                             "ver": version_id})).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return content_response(row)
