"""Question answering and conversations (TECH-V2-ai-service §7.2, §7.5).

``POST /ai/v1/conversations/{id}/messages`` streams server-sent events. The other routes read and
rename the caller's own conversations. A conversation that is not the caller's is a ``404``, the
same as one that does not exist.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.auth.jwt import current_principal
from sopilot_ai.conversations import repository as repo
from sopilot_ai.conversations.events import PING, Event
from sopilot_ai.conversations.service import ConversationNotFound, QAService
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.retrieval.access_filter import Principal

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/ai/v1", tags=["conversations"])

PING_SECONDS = 15.0
# Larger than the 1000-character question limit on purpose: a question between the two gets the
# fixed "too long" sentence (D4); only an absurd body is rejected before the pipeline.
MAX_BODY_CHARS = 20_000
TITLE_MAX = 200


class MessageIn(BaseModel):
    content: str = Field(max_length=MAX_BODY_CHARS)
    lang: Literal["vi", "en"] | None = None


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX)


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


async def get_qa_service(request: Request) -> QAService:
    """The service, built on first use (it loads the embedding model and the LLM chains)."""
    factory = request.app.state.qa_service_factory
    try:
        return await factory()
    except Exception as exc:  # noqa: BLE001 - configuration problems must not reach the client
        log.error("qa_service_unavailable", error=type(exc).__name__)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "question answering is not available") from exc


async def with_pings(events: AsyncIterator[Event], interval: float = PING_SECONDS
                     ) -> AsyncIterator[str]:
    """SSE text of ``events``; a ``: ping`` comment goes out after ``interval`` of silence."""
    it = events.__aiter__()
    pending: asyncio.Future[Event] = asyncio.ensure_future(it.__anext__())
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield PING
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            yield event.sse()
            pending = asyncio.ensure_future(it.__anext__())
    finally:
        if pending.done():
            # The source is idle, suspended at a yield: close it so it can store the abort.
            aclose = getattr(it, "aclose", None)
            if aclose is not None:
                await aclose()
        else:
            # The source is inside a running __anext__: cancel that call and let the source
            # unwind itself. Closing it now would raise "asynchronous generator is already running".
            pending.cancel()


def _conversation_id(raw: str) -> UUID | None:
    """``new`` starts a conversation; anything else must be a UUID (else it simply is not found)."""
    if raw == "new":
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found") from exc


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: str,
    body: MessageIn,
    principal: Annotated[Principal, Depends(current_principal)],
    service: Annotated[QAService, Depends(get_qa_service)],
) -> StreamingResponse:
    try:
        ref = await service.open(principal, _conversation_id(conversation_id))
    except ConversationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found") from exc
    stream = with_pings(service.answer(principal, ref, body.content, body.lang))
    return StreamingResponse(stream, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
async def list_conversations(
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        rows = await repo.list_conversations(conn, principal, limit=limit, offset=offset)
    return [{"id": str(r.id), "title": r.title, "createdAt": r.created_at.isoformat(),
             "updatedAt": r.updated_at.isoformat()} for r in rows]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> dict[str, Any]:
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        detail = await repo.conversation_detail(conn, principal, conversation_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    return detail


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: UUID,
    body: ConversationPatch,
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> dict[str, Any]:
    title = " ".join(body.title.split())
    if not title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "title must not be blank")
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        found = await repo.rename(conn, principal, conversation_id, title)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    return {"id": str(conversation_id), "title": title}


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    principal: Annotated[Principal, Depends(current_principal)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> None:
    async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
        found = await repo.soft_delete(conn, principal, conversation_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
