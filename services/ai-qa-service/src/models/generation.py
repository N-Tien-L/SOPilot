from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID

from .retrieval import RetrievalChunk


class GenerationResult(BaseModel):
    content: str
    model_used: str
    model_name_actual: Optional[str] = None
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    latency_ms: int


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    model_id: str = "default"
    context: Optional[Dict[str, Any]] = None


class SourceDocument(BaseModel):
    document_id: UUID
    document_name: str
    relevance_score: float
    excerpt: str


class ChatResponse(BaseModel):
    message: "MessageResponse"
    conversation: "ConversationResponse"
    sources: Optional[List[SourceDocument]] = None


from .message import MessageResponse, MessageRole
from .conversation import ConversationResponse