import structlog
from uuid import UUID
from typing import Optional

from ..session import get_connection, release_connection

logger = structlog.get_logger(__name__)


class UnansweredQuestionRepository:
    async def create(
        self,
        user_id: UUID,
        question: str,
        message_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
        search_query: Optional[str] = None,
        top_similarity_score: Optional[float] = None,
        priority: str = "NORMAL",
        user_department_id: Optional[UUID] = None,
        user_role: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> UUID:
        import json
        
        query = """
            INSERT INTO conversation.unanswered_questions (
                user_id, message_id, conversation_id,
                question, search_query, top_similarity_score,
                priority, user_department_id, user_role,
                metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
            ) RETURNING id
        """
        
        meta_json = json.dumps(metadata) if metadata else '{}'
        
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                query,
                user_id,
                message_id,
                conversation_id,
                question,
                search_query,
                top_similarity_score,
                priority,
                user_department_id,
                user_role,
                meta_json
            )
            return row['id']
        except Exception as e:
            logger.error("db_error", action="create_unanswered_question", error=str(e))
            raise
        finally:
            await release_connection(conn)

unanswered_question_repo = UnansweredQuestionRepository()
