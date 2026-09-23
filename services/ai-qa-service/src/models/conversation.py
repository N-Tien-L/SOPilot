from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List
from datetime import datetime


class ConversationBase(BaseModel):
    title: Optional[str] = None


class ConversationCreate(ConversationBase):
    user_id: UUID


class ConversationUpdate(ConversationBase):
    pass


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    workspace_id: Optional[UUID] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    items: List[ConversationResponse]
    page: int
    size: int
    total: int
