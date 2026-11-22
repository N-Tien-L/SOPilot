"""Processing report: detected family, chunking strategy, chunk layout (§7.7, V2-46).

Same access rule as ``/content`` (§7.3): the active version of a document the asker may
read, otherwise one 404. The list carries no chunk text; one chunk's text is read with
``?ordinal=``.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.auth.jwt import current_principal
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.docproc.chunk.family import DocFamily, family_evidence
from sopilot_ai.docproc.chunk.headings import resolve_outline
from sopilot_ai.docproc.model import StructuredDocument
from sopilot_ai.providers.registry import ModelsConfig
from sopilot_ai.retrieval.access_filter import Principal, access_params, allowed_cte

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/ai/v1", tags=["documents"])

# Rule ids per family; the frontend owns the wording. Mirrors ``Chunker`` (family.py, chunker.py).
STRATEGY_RULES: dict[str, list[str]] = {
    DocFamily.LEGAL_ARTICLES.value: ["HEADING_TREE", "ARTICLE_UNIT", "STEP_ROW", "PACK", "PREFIX"],
    DocFamily.ISO_PROCEDURE.value: ["HEADING_TREE", "MERGE_SHORT", "STEP_ROW", "PACK", "PREFIX"],
    DocFamily.MARKDOWN.value: ["HEADING_TREE", "MERGE_SHORT", "PACK", "PREFIX"],
    DocFamily.PROSE.value: ["PACK", "PREFIX"],
}

_REPORT = text(f"""
WITH {allowed_cte()}
SELECT e.document_id, e.version_id, e.structure->>'file_type' AS file_type, e.doc_family,
       e.language, e.page_count, e.extracted_meta->>'docCode' AS doc_code, e.structure
  FROM rag.extracted_documents e
  JOIN allowed a ON a.document_id = e.document_id AND a.active_version_id = e.version_id
 WHERE e.workspace_id = :wid AND e.document_id = :doc AND e.version_id = :ver
""")

_CHUNKS = text("""
SELECT c.ordinal, c.chunk_type, c.section_path, c.page_start, c.page_end,
       c.char_start, c.char_end, c.token_count
  FROM rag.chunks c
 WHERE c.workspace_id = :wid AND c.document_id = :doc AND c.version_id = :ver
 ORDER BY c.ordinal
""")

_CHUNK = text("""
SELECT c.ordinal, c.chunk_type, c.section_path, c.token_count, c.content, c.index_text
  FROM rag.chunks c
 WHERE c.workspace_id = :wid AND c.document_id = :doc AND c.version_id = :ver
   AND c.ordinal = :ordinal
""")

_REQUEST_CONFIG_KEY = "chunk_config"


def signals_from(structure: Any) -> dict[str, object] | None:
    """Recomputed with the ingest functions from the stored elements; ``None`` if unreadable."""
    try:
        elements = StructuredDocument.model_validate(structure).elements
        return family_evidence(resolve_outline(elements))
    except Exception:  # noqa: BLE001 - the report must still render without the evidence
        log.warning("processing_report_signals_unreadable")
        return None


def stats_of(rows: Sequence[Any]) -> dict[str, object]:
    tokens = [int(r.token_count) for r in rows]
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r.chunk_type] = by_type.get(r.chunk_type, 0) + 1
    return {
        "chunks": len(rows),
        "avgTokens": round(sum(tokens) / len(tokens)) if tokens else 0,
        "maxTokens": max(tokens, default=0),
        "byType": by_type,
    }


def report_response(row: Any, chunk_rows: Sequence[Any], config: dict[str, int]) -> dict[str, Any]:
    return {
        "documentId": str(row.document_id),
        "versionId": str(row.version_id),
        "fileType": row.file_type,
        "language": row.language,
        "docCode": row.doc_code,
        "pageCount": row.page_count,
        "family": row.doc_family,
        "signals": signals_from(row.structure),
        "strategy": {"rules": STRATEGY_RULES.get(row.doc_family, []), "config": config},
        "stats": stats_of(chunk_rows),
        "chunks": [
            {"ordinal": r.ordinal, "chunkType": r.chunk_type, "sectionPath": list(r.section_path),
             "pageStart": r.page_start, "pageEnd": r.page_end, "charStart": r.char_start,
             "charEnd": r.char_end, "tokenCount": r.token_count}
            for r in chunk_rows
        ],
    }


def chunk_response(row: Any) -> dict[str, Any]:
    return {"ordinal": row.ordinal, "chunkType": row.chunk_type,
            "sectionPath": list(row.section_path), "tokenCount": row.token_count,
            "content": row.content, "indexText": row.index_text}


def _chunk_config(request: Request) -> dict[str, int]:
    """The ``chunking`` section of ``models.yaml`` as it is now (not stored per version)."""
    cached = getattr(request.app.state, _REQUEST_CONFIG_KEY, None)
    if cached is None:
        cfg = ModelsConfig.load(request.app.state.models_config_path).chunking()
        cached = {"targetTokens": cfg.target_tokens, "maxTokens": cfg.max_tokens,
                  "minTokens": cfg.min_tokens}
        setattr(request.app.state, _REQUEST_CONFIG_KEY, cached)
    return cached


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


@router.get("/documents/{document_id}/versions/{version_id}/processing-report")
async def processing_report(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    ordinal: Annotated[int | None, Query(ge=0)] = None,
) -> dict[str, Any]:
    params = {**access_params(principal), "doc": document_id, "ver": version_id}
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        row = (await conn.execute(_REPORT, params)).first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
        if ordinal is not None:
            chunk = (await conn.execute(_CHUNK, {**params, "ordinal": ordinal})).first()
            if chunk is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
            return chunk_response(chunk)
        chunk_rows = (await conn.execute(_CHUNKS, params)).all()
    return report_response(row, chunk_rows, _chunk_config(request))
