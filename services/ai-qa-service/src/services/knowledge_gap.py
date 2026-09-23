from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from enum import Enum
import structlog
import json
from datetime import datetime

from ..config.settings import settings
from ..config.rabbitmq import publisher
from .retrieval.hybrid_search import hybrid_search_service
from ..models.retrieval import RetrievalChunk

logger = structlog.get_logger()


class PriorityLevel(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UnansweredQuestionResult(BaseModel):
    is_unanswered: bool
    reason: Optional[str] = None
    top_similarity: float
    search_query: Optional[str] = None
    priority: Optional[str] = "NORMAL"


class KnowledgeGapDetector:
    def __init__(self):
        self.threshold = settings.similarity_threshold

    async def evaluate(
        self,
        query: str,
        retrieved_chunks: list[RetrievalChunk]
    ) -> UnansweredQuestionResult:
        if not retrieved_chunks:
            return UnansweredQuestionResult(
                is_unanswered=True,
                reason="no_chunks_retrieved",
                top_similarity=0.0
            )

        top_similarity = retrieved_chunks[0].similarity_score

        if top_similarity < self.threshold:
            return UnansweredQuestionResult(
                is_unanswered=True,
                reason="low_relevance",
                top_similarity=top_similarity,
                search_query=query,
                priority=self._determine_priority(top_similarity)
            )

        return UnansweredQuestionResult(
            is_unanswered=False,
            top_similarity=top_similarity
        )

    def _determine_priority(self, similarity: float) -> str:
        if similarity < 0.1:
            return "CRITICAL"
        elif similarity < 0.2:
            return "HIGH"
        else:
            return "NORMAL"

    async def publish_unanswered(
        self,
        result: UnansweredQuestionResult,
        user_id: UUID,
        conversation_id: UUID,
        question: str,
        message_id: Optional[UUID] = None,
        user_department_id: Optional[UUID] = None,
        user_role: str = "USER"
    ):
        if not result.is_unanswered:
            return

        event = {
            "event_type": "unanswered.question",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
            "payload": {
                "user_id": str(user_id),
                "message_id": str(message_id),
                "conversation_id": str(conversation_id),
                "question": question,
                "search_query": result.search_query or question,
                "top_similarity_score": result.top_similarity,
                "priority": result.priority,
                "user_department_id": str(user_department_id) if user_department_id else None,
                "user_role": user_role
            }
        }

        try:
            await publisher.publish_json("unanswered.question", event)
            logger.info("unanswered_question_published", message_id=str(message_id))
        except Exception as e:
            logger.error("failed_to_publish_unanswered", error=str(e))


knowledge_gap_detector = KnowledgeGapDetector()