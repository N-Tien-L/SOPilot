from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Any, Dict
from datetime import datetime

import structlog

from ...config.settings import settings
from ...services.orchestrator.pipeline import PipelineOrchestrator
from ...services.rate_limiter import rate_limit
from ...db.repositories.message_repo import message_repository
from ..dependencies import get_user_context, UserContext
from ...services.conversation.manager import conversation_service
from ...models.conversation import ConversationResponse
from ...models.message import MessageResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    context_window: Optional[int] = None
    use_knowledge: bool = True
    use_websearch: bool = False
    use_layer2: bool = True
    filters: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    answer: str
    conversationId: UUID
    message: MessageResponse
    conversation: ConversationResponse
    sources: Optional[list] = None


orchestrator = PipelineOrchestrator()


def _normalize_sources(result) -> Optional[list]:
    if not result.sources:
        return None
    return [
        {
            "document_id": str(chunk.document_id),
            "content": chunk.content[:300],
            "score": chunk.similarity_score,
            "chunk_index": chunk.chunk_index,
        }
        for chunk in result.sources
    ]


def _build_chat_response(result, request, conv, assistant_msg, sources_data):
    """Format PipelineResult into ChatResponse."""
    return ChatResponse(
        answer=assistant_msg.content,
        conversationId=conv.id,
        message=MessageResponse(
            id=assistant_msg.id,
            conversation_id=assistant_msg.conversation_id,
            role=assistant_msg.role.value,
            content=assistant_msg.content,
            sources=assistant_msg.sources,
            model_used=assistant_msg.model_used,
            tokens_prompt=assistant_msg.tokens_prompt,
            tokens_completion=assistant_msg.tokens_completion,
            tokens_total=assistant_msg.tokens_total,
            latency_ms=assistant_msg.latency_ms,
            confidence=assistant_msg.confidence.value if assistant_msg.confidence else None,
            has_sources=assistant_msg.has_sources,
            created_at=assistant_msg.created_at,
        ),
        conversation=ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            message_count=conv.message_count,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ),
        sources=sources_data,
    )


@router.post("", response_model=ChatResponse, dependencies=[Depends(rate_limit)])
async def chat(request: ChatRequest, user: UserContext = Depends(get_user_context)):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if request.conversation_id:
        conv = await conversation_service.get_conversation(request.conversation_id, user.user_id, user.workspace_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = await conversation_service.create_conversation(user.user_id, workspace_id=user.workspace_id)
        request.conversation_id = conv.id

    await conversation_service.add_message(
        request.conversation_id,
        role="USER",
        content=request.message,
        has_sources=False,
        workspace_id=user.workspace_id,
    )

    result = await orchestrator.process(request, user)

    if result.status == "BLOCKED":
        # Mark the last USER message as toxic
        await message_repository.mark_last_user_message_toxic(
            request.conversation_id, user.user_id
        )
        assistant_msg = await conversation_service.add_message(
            request.conversation_id,
            role="ASSISTANT",
            content=result.response,
            has_sources=False,
            workspace_id=user.workspace_id,
        )
        return _build_chat_response(result, request, conv, assistant_msg, None)

    if result.layer_stopped == 2:
        conv = await conversation_service.get_conversation(request.conversation_id, user.user_id, user.workspace_id)
        assistant_msg = await conversation_service.add_message(
            request.conversation_id,
            role="ASSISTANT",
            content=result.response,
            model_used=result.model_used,
            latency_ms=result.latency_ms,
            has_sources=False,
            workspace_id=user.workspace_id,
        )
        return _build_chat_response(result, request, conv, assistant_msg, None)

    # Layer 3: RAG response
    conv = await conversation_service.get_conversation(request.conversation_id, user.user_id, user.workspace_id)
    assistant_msg = await message_repository.get_by_id(
        conv.id, user.user_id
    ) if conv else None

    # Re-fetch to get the latest message
    messages = await message_repository.get_by_conversation(
        request.conversation_id, user.user_id, limit=1
    )
    assistant_msg = messages[-1] if messages else None

    return _build_chat_response(result, request, conv, assistant_msg, result.sources)


@router.post("/stream", dependencies=[Depends(rate_limit)])
async def chat_stream(request: ChatRequest, user: UserContext = Depends(get_user_context)):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if request.conversation_id:
        conv = await conversation_service.get_conversation(request.conversation_id, user.user_id, user.workspace_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = await conversation_service.create_conversation(user.user_id, workspace_id=user.workspace_id)
        request.conversation_id = conv.id

    await conversation_service.add_message(
        request.conversation_id,
        role="USER",
        content=request.message,
        has_sources=False,
        workspace_id=user.workspace_id,
    )

    return StreamingResponse(
        orchestrator.process_stream(request, user),
        media_type="text/event-stream",
    )
