from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class SourceDocument(BaseModel):
    document_id: UUID
    document_name: str
    relevance_score: float
    excerpt: str


class MessageCreate(BaseModel):
    conversation_id: UUID
    role: MessageRole
    content: str
    sources: Optional[List[dict]] = None
    model_used: Optional[str] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    tokens_total: Optional[int] = None
    latency_ms: Optional[int] = None
    confidence: Optional[ConfidenceLevel] = None
    has_sources: bool = False
    is_toxic: bool = False
    is_layer2_response: bool = False


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    sources: Optional[Any] = None
    model_used: Optional[str] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    tokens_total: Optional[int] = None
    latency_ms: Optional[int] = None
    confidence: Optional[ConfidenceLevel] = None
    has_sources: bool = False
    metadata: Optional[dict] = None
    is_streaming: bool = False
    streaming_completed: bool = True
    is_toxic: bool = False
    is_layer2_response: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    items: List[MessageResponse]