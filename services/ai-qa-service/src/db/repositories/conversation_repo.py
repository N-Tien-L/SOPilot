from uuid import UUID
from typing import List, Optional, Tuple
from datetime import datetime
import asyncpg
import structlog

from ...db.session import get_connection, release_connection
from ...models.conversation import ConversationCreate, ConversationResponse

logger = structlog.get_logger()


class ConversationRepository:
    async def create(
        self,
        user_id: UUID,
        title: Optional[str] = None,
        workspace_id: Optional[UUID] = None,
    ) -> ConversationResponse:
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                """INSERT INTO conversation.conversations (user_id, title, workspace_id, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $4)
                   RETURNING id, user_id, title, workspace_id, message_count, last_message_at, created_at, updated_at""",
                user_id, title, workspace_id, datetime.utcnow()
            )
            return ConversationResponse(**dict(row))
        finally:
            await release_connection(conn)

    async def get_by_id(
        self,
        conversation_id: UUID,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
    ) -> Optional[ConversationResponse]:
        conn = await get_connection()
        try:
            if workspace_id is not None:
                row = await conn.fetchrow(
                    """SELECT id, user_id, title, workspace_id, message_count, last_message_at, created_at, updated_at
                       FROM conversation.conversations
                       WHERE id = $1 AND user_id = $2 AND workspace_id = $3 AND deleted_at IS NULL""",
                    conversation_id, user_id, workspace_id
                )
            else:
                row = await conn.fetchrow(
                    """SELECT id, user_id, title, workspace_id, message_count, last_message_at, created_at, updated_at
                       FROM conversation.conversations
                       WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL""",
                    conversation_id, user_id
                )
            if not row:
                return None
            return ConversationResponse(**dict(row))
        finally:
            await release_connection(conn)

    async def list_by_user(
        self,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
        workspace_id: Optional[UUID] = None,
    ) -> Tuple[List[ConversationResponse], int]:
        conn = await get_connection()
        try:
            offset = (page - 1) * size

            where_clause = "WHERE user_id = $1 AND deleted_at IS NULL"
            params: List = [user_id]
            param_idx = 2

            if workspace_id is not None:
                where_clause += f" AND workspace_id = ${param_idx}"
                params.append(workspace_id)
                param_idx += 1

            if keyword:
                where_clause += f" AND title ILIKE ${param_idx}"
                params.append(f"%{keyword}%")
                param_idx += 1

            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM conversation.conversations {where_clause}",
                *params
            )

            rows = await conn.fetch(
                f"""SELECT id, user_id, title, workspace_id, message_count, last_message_at, created_at, updated_at
                    FROM conversation.conversations
                    {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT ${param_idx} OFFSET ${param_idx + 1}""",
                *params, size, offset
            )

            return [ConversationResponse(**dict(row)) for row in rows], total
        finally:
            await release_connection(conn)

    async def delete(
        self,
        conversation_id: UUID,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
    ) -> bool:
        conn = await get_connection()
        try:
            if workspace_id is not None:
                result = await conn.execute(
                    """UPDATE conversation.conversations
                       SET deleted_at = $4
                       WHERE id = $1 AND user_id = $2 AND workspace_id = $3 AND deleted_at IS NULL""",
                    conversation_id, user_id, workspace_id, datetime.utcnow()
                )
            else:
                result = await conn.execute(
                    """UPDATE conversation.conversations
                       SET deleted_at = $3
                       WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL""",
                    conversation_id, user_id, datetime.utcnow()
                )
            return result != "UPDATE 0"
        finally:
            await release_connection(conn)

    async def update_title_if_default(self, conversation_id: UUID, title: str) -> None:
        conn = await get_connection()
        try:
            await conn.execute(
                """UPDATE conversation.conversations
                   SET title = $2,
                       updated_at = $3
                   WHERE id = $1 AND (title = 'New Conversation' OR title IS NULL)""",
                conversation_id, title, datetime.utcnow()
            )
        finally:
            await release_connection(conn)

    async def update_title(self, conversation_id: UUID, title: str) -> None:
        conn = await get_connection()
        try:
            await conn.execute(
                """UPDATE conversation.conversations
                   SET title = $2,
                       updated_at = $3
                   WHERE id = $1""",
                conversation_id, title, datetime.utcnow()
            )
        finally:
            await release_connection(conn)

    async def update_message_count(self, conversation_id: UUID) -> None:
        conn = await get_connection()
        try:
            await conn.execute(
                """UPDATE conversation.conversations
                   SET message_count = message_count + 1,
                       last_message_at = $2,
                       updated_at = $2
                   WHERE id = $1""",
                conversation_id, datetime.utcnow()
            )
        finally:
            await release_connection(conn)


conversation_repository = ConversationRepository()