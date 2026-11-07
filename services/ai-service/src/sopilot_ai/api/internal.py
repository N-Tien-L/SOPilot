"""Internal API called by core-api (TECH-V2-ai-service §8, TECH-V2-core-api §8.1).

Mounted at ``/internal``, never under ``/ai``, so the frontend rewrites cannot reach it.
"""
from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.db.repositories import access, idempotency, jobs
from sopilot_ai.ingest.schemas import AccessSpec, IngestionRequest

router = APIRouter(prefix="/internal", tags=["internal"])


class AccessUpdate(AccessSpec):
    """``PUT /internal/document-access/{documentId}`` body (TECH-V2-core-api §8.1)."""

    workspace_id: UUID = Field(alias="workspaceId")


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def require_internal_token(
    request: Request,
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected: str = request.app.state.internal_token
    given = (x_internal_token or "").encode("utf-8")
    if not expected or not hmac.compare_digest(given, expected.encode("utf-8")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid internal token")


@router.post("/ingestions", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_internal_token)])
async def create_ingestion(
    body: IngestionRequest,
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> dict[str, bool]:
    """Write ``document_access`` (when newer) and the job in one transaction (§2.1, §8).

    ``queued`` is false for a repeated key, the same ``attempt`` again, or a job that is not
    ``FAILED``; core-api treats every ``202`` as delivered.
    """
    async with tenant_tx(engine, body.workspace_id) as conn:
        if not await idempotency.claim_key(conn, idempotency_key):
            return {"queued": False}
        await access.upsert_access(
            conn, workspace_id=body.workspace_id, document_id=body.document_id,
            visibility=body.access.visibility, department_ids=body.access.department_ids,
            access_revision=body.access.access_revision, title=body.title)
        queued = await jobs.enqueue(
            conn, workspace_id=body.workspace_id, document_id=body.document_id,
            version_id=body.version_id, request_attempt=body.attempt,
            payload=body.model_dump(mode="json", by_alias=True))
    return {"queued": queued}


@router.put("/document-access/{document_id}", dependencies=[Depends(require_internal_token)])
async def update_document_access(
    document_id: UUID,
    body: AccessUpdate,
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> dict[str, bool]:
    """``applied`` is false when ``accessRevision`` is not newer, or the key was seen."""
    async with tenant_tx(engine, body.workspace_id) as conn:
        if not await idempotency.claim_key(conn, idempotency_key):
            return {"applied": False}
        applied = await access.update_access(
            conn, workspace_id=body.workspace_id, document_id=document_id,
            visibility=body.visibility, department_ids=body.department_ids,
            access_revision=body.access_revision)
    return {"applied": applied}


@router.delete("/documents/{document_id}", dependencies=[Depends(require_internal_token)])
async def delete_document(
    document_id: UUID,
    workspace_id: Annotated[UUID, Query(alias="workspaceId")],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> dict[str, bool]:
    """Remove the document from retrieval and delete its data; idempotent (``200`` always)."""
    async with tenant_tx(engine, workspace_id) as conn:
        if await idempotency.claim_key(conn, idempotency_key):
            await access.delete_document(conn, workspace_id=workspace_id, document_id=document_id)
    return {"deleted": True}
