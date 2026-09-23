from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from ..dependencies import get_user_context, UserContext
from ...db.repositories.message_repo import message_repository

router = APIRouter(tags=["Messages"])


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    sources: Optional[list] = None
    model_used: Optional[str] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    tokens_total: Optional[int] = None
    latency_ms: Optional[int] = None
    confidence: Optional[str] = None
    has_sources: bool = False
    is_streaming: bool = False
    streaming_completed: bool = True
    created_at: datetime


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    user: UserContext = Depends(get_user_context)
):
    from ...services.conversation.manager import conversation_service

    conv = await conversation_service.get_conversation(conversation_id, user.user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await message_repository.get_by_conversation(conversation_id, user.user_id)
    return messages


@router.delete("/conversations/{conversation_id}/messages")
async def clear_messages(
    conversation_id: UUID,
    user: UserContext = Depends(get_user_context)
):
    from ...services.conversation.manager import conversation_service

    conv = await conversation_service.get_conversation(conversation_id, user.user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await message_repository.delete_by_conversation(conversation_id, user.user_id)
    return {"message": "Messages cleared"}