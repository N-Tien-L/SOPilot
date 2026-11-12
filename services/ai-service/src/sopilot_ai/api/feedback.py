"""Answer feedback and the knowledge-gap list (TECH-V2-ai-service §7.6, FR-16, FR-17).

Feedback is for the conversation's owner. The gap list is for OWNER and ADMIN; a MEMBER gets
``403`` (the role comes from the verified token, so the answer does not depend on the resource).
A message that is not the caller's, or not a gap, is ``404``.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.api.conversations import get_engine
from sopilot_ai.auth.jwt import current_principal
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.feedback import repository as repo
from sopilot_ai.qa import pii
from sopilot_ai.retrieval.access_filter import Principal

router = APIRouter(prefix="/ai/v1", tags=["feedback"])

COMMENT_MAX = 1000
NOTE_MAX = 1000
ADMIN_ROLES = ("OWNER", "ADMIN")


class FeedbackIn(BaseModel):
    vote: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=COMMENT_MAX)

    @field_validator("comment")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None


class ResolveIn(BaseModel):
    note: str | None = Field(default=None, max_length=NOTE_MAX)


def _masked(text: str | None) -> str | None:
    return None if text is None else pii.mask_pii(text).text


def _gap_out(row: Any, comments: list[Any]) -> dict[str, Any]:
    return {
        "messageId": str(row.id),
        "question": _masked(row.question),
        "outcome": row.outcome,
        "refusalReason": row.refusal_reason,
        "askedAt": row.created_at.isoformat(),
        "upvotes": int(row.upvotes),
        "downvotes": int(row.downvotes),
        "comments": [{"vote": c.vote, "comment": _masked(c.comment)} for c in comments],
        "status": "resolved" if row.resolved_at else "open",
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolutionNote": row.resolution_note,
    }


@router.put("/messages/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def put_feedback(
    message_id: UUID,
    body: FeedbackIn,
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> None:
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        found = await repo.upsert_feedback(conn, principal, message_id, body.vote, body.comment)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")


@router.get("/knowledge-gaps")
async def list_gaps(
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    gap_status: Annotated[Literal["open", "resolved"], Query(alias="status")] = "open",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    if principal.role not in ADMIN_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "owner or admin required")
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        rows, comments = await repo.gap_list(conn, principal, status=gap_status, limit=limit,
                                             offset=offset)
    return [_gap_out(r, comments.get(r.id, [])) for r in rows]


@router.post("/knowledge-gaps/{message_id}/resolve")
async def resolve_gap(
    message_id: UUID,
    body: ResolveIn,
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> dict[str, Any]:
    if principal.role not in ADMIN_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "owner or admin required")
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        found = await repo.resolve_gap(conn, principal, message_id, body.note)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "knowledge gap not found")
    return {"messageId": str(message_id), "status": "resolved"}
