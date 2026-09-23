from uuid import UUID
from typing import List, Optional
from datetime import datetime
import asyncpg
import json
import structlog

from ...db.session import get_connection, release_connection
from ...models.message import MessageResponse, MessageRole, ConfidenceLevel

logger = structlog.get_logger()


class MessageRepository:
    async def create(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        sources: Optional[list] = None,
        model_used: Optional[str] = None,
        tokens_prompt: Optional[int] = None,
        tokens_completion: Optional[int] = None,
        tokens_total: Optional[int] = None,
        latency_ms: Optional[int] = None,
        confidence: Optional[str] = None,
        has_sources: bool = False,
        metadata: Optional[dict] = None,
        is_toxic: bool = False,
        is_layer2_response: bool = False,
        workspace_id: Optional[UUID] = None,
    ) -> MessageResponse:
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                """INSERT INTO conversation.messages
                   (conversation_id, role, content, sources, model_used, tokens_prompt,
                    tokens_completion, tokens_total, latency_ms, confidence, has_sources, metadata,
                    is_toxic, is_layer2_response, created_at, workspace_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                   RETURNING id, conversation_id, role, content, sources, model_used,
                             tokens_prompt, tokens_completion, tokens_total, latency_ms,
                             confidence, has_sources, metadata, is_streaming, streaming_completed,
                             is_toxic, is_layer2_response, created_at, workspace_id""",
                conversation_id,
                role,
                content,
                json.dumps(sources, default=str) if sources else None,
                model_used,
                tokens_prompt,
                tokens_completion,
                tokens_total,
                latency_ms,
                confidence,
                has_sources,
                json.dumps(metadata) if metadata else '{}',
                is_toxic,
                is_layer2_response,
                datetime.utcnow(),
                workspace_id
            )
            row_dict = dict(row)
            if row_dict.get('sources') and isinstance(row_dict['sources'], str):
                row_dict['sources'] = json.loads(row_dict['sources'])
            if row_dict.get('metadata') and isinstance(row_dict['metadata'], str):
                row_dict['metadata'] = json.loads(row_dict['metadata'])
            return MessageResponse(**row_dict)
        finally:
            await release_connection(conn)

    async def get_by_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: int = 50,
        exclude_layer2: bool = False,
        exclude_toxic: bool = False,
    ) -> List[MessageResponse]:
        conn = await get_connection()
        try:
            where_clauses = [
                "m.conversation_id = $1",
                "c.user_id = $2",
                "m.deleted_at IS NULL"
            ]
            params = [conversation_id, user_id]
            param_idx = 3

            if exclude_layer2:
                where_clauses.append(f"m.is_layer2_response = ${param_idx}")
                params.append(False)
                param_idx += 1

            if exclude_toxic:
                where_clauses.append(f"m.is_toxic = ${param_idx}")
                params.append(False)
                param_idx += 1

            where_clause = " AND ".join(where_clauses)
            params.append(limit)

            rows = await conn.fetch(
                f"""SELECT m.id, m.conversation_id, m.role, m.content, m.sources, m.model_used,
                          m.tokens_prompt, m.tokens_completion, m.tokens_total, m.latency_ms,
                          m.confidence, m.has_sources, m.metadata, m.is_streaming, m.streaming_completed,
                          m.is_toxic, m.is_layer2_response, m.created_at, m.workspace_id
                   FROM conversation.messages m
                   JOIN conversation.conversations c ON m.conversation_id = c.id
                   WHERE {where_clause}
                   ORDER BY m.created_at ASC
                   LIMIT ${param_idx}""",
                *params
            )
            results = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('sources') and isinstance(row_dict['sources'], str):
                    row_dict['sources'] = json.loads(row_dict['sources'])
                if row_dict.get('metadata') and isinstance(row_dict['metadata'], str):
                    row_dict['metadata'] = json.loads(row_dict['metadata'])
                results.append(MessageResponse(**row_dict))
            return results
        finally:
            await release_connection(conn)

    async def get_by_id(self, message_id: UUID, user_id: UUID) -> Optional[MessageResponse]:
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                """SELECT m.id, m.conversation_id, m.role, m.content, m.sources, m.model_used,
                          m.tokens_prompt, m.tokens_completion, m.tokens_total, m.latency_ms,
                          m.confidence, m.has_sources, m.metadata, m.is_streaming, m.streaming_completed,
                          m.is_toxic, m.is_layer2_response, m.created_at, m.workspace_id
                   FROM conversation.messages m
                   JOIN conversation.conversations c ON m.conversation_id = c.id
                   WHERE m.id = $1 AND c.user_id = $2 AND m.deleted_at IS NULL""",
                message_id, user_id
            )
            if not row:
                return None
            row_dict = dict(row)
            if row_dict.get('sources') and isinstance(row_dict['sources'], str):
                row_dict['sources'] = json.loads(row_dict['sources'])
            if row_dict.get('metadata') and isinstance(row_dict['metadata'], str):
                row_dict['metadata'] = json.loads(row_dict['metadata'])
            return MessageResponse(**row_dict)
        finally:
            await release_connection(conn)

    async def delete_by_conversation(self, conversation_id: UUID, user_id: UUID) -> bool:
        conn = await get_connection()
        try:
            result = await conn.execute(
                """UPDATE conversation.messages
                   SET deleted_at = $3
                   WHERE conversation_id = $1
                   AND EXISTS (SELECT 1 FROM conversation.conversations WHERE id = $1 AND user_id = $2)
                   AND deleted_at IS NULL""",
                conversation_id, user_id, datetime.utcnow()
            )
            return True
        finally:
            await release_connection(conn)

    async def mark_last_user_message_toxic(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        """Mark the last USER message in a conversation as toxic/blocked."""
        conn = await get_connection()
        try:
            await conn.execute(
                """UPDATE conversation.messages
                   SET is_toxic = TRUE
                   WHERE id = (
                       SELECT m.id FROM conversation.messages m
                       JOIN conversation.conversations c ON m.conversation_id = c.id
                       WHERE m.conversation_id = $1
                       AND c.user_id = $2
                       AND m.role = 'USER'
                       AND m.deleted_at IS NULL
                       ORDER BY m.created_at DESC
                       LIMIT 1
                   )""",
                conversation_id, user_id
            )
        finally:
            await release_connection(conn)


message_repository = MessageRepository()
