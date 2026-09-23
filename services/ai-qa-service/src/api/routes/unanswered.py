from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

from ..dependencies import get_user_context, UserContext

router = APIRouter(tags=["Unanswered Questions"])


class UnansweredQuestionResponse(BaseModel):
    id: UUID
    user_id: UUID
    message_id: UUID
    conversation_id: UUID
    question: str
    question_normalized: str
    attempted_context: Optional[dict] = None
    search_query: str
    top_similarity_score: float
    user_department_id: Optional[UUID] = None
    user_role: str
    resolved: bool = False
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    related_document_id: Optional[UUID] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@router.post("/conversations/{conversation_id}/messages/{message_id}/unanswered")
async def mark_unanswered(
    conversation_id: UUID,
    message_id: UUID,
    user: UserContext = Depends(get_user_context)
):
    if user.role not in ["MANAGER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only MANAGER and ADMIN can mark questions as unanswered"
        )

    from ...services.conversation.manager import conversation_service
    from ...db.repositories.message_repo import message_repository

    conv = await conversation_service.get_conversation(conversation_id, user.user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message = await message_repository.get_by_id(message_id, user.user_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    from ...db.session import get_connection, release_connection

    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            """INSERT INTO conversation.unanswered_questions
               (user_id, message_id, conversation_id, question, search_query,
                top_similarity_score, user_department_id, user_role, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
               RETURNING id, user_id, message_id, conversation_id, question, question_normalized,
                         attempted_context, search_query, top_similarity_score, user_department_id,
                         user_role, resolved, resolved_by, resolved_at, resolution_notes,
                         related_document_id, category, priority, created_at, updated_at""",
            user.user_id, message_id, conversation_id, message.content, message.content,
            0.0, user.department_id, user.role, datetime.utcnow()
        )
        return UnansweredQuestionResponse(**dict(row))
    finally:
        await release_connection(conn)