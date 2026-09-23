from uuid import UUID
from typing import List, Optional
from datetime import datetime
import structlog

from ...db.repositories.conversation_repo import conversation_repository
from ...db.repositories.message_repo import message_repository
from ...models.conversation import ConversationResponse, ConversationCreate

logger = structlog.get_logger()


class ConversationService:
    def __init__(self):
        self.conv_repo = conversation_repository
        self.msg_repo = message_repository

    async def create_conversation(
        self,
        user_id: UUID,
        title: Optional[str] = None,
        workspace_id: Optional[UUID] = None
    ) -> ConversationResponse:
        if not title:
            title = "New Conversation"

        return await self.conv_repo.create(user_id, title, workspace_id)

    async def get_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
        workspace_id: Optional[UUID] = None
    ) -> Optional[ConversationResponse]:
        return await self.conv_repo.get_by_id(conversation_id, user_id, workspace_id)

    async def list_conversations(
        self,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
        workspace_id: Optional[UUID] = None
    ) -> tuple[List[ConversationResponse], int]:
        return await self.conv_repo.list_by_user(user_id, page, size, keyword, workspace_id)

    async def delete_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
        workspace_id: Optional[UUID] = None
    ) -> bool:
        await self.msg_repo.delete_by_conversation(conversation_id, user_id)
        return await self.conv_repo.delete(conversation_id, user_id, workspace_id)

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        workspace_id: Optional[UUID] = None,
        **kwargs
    ):
        message = await self.msg_repo.create(
            conversation_id=conversation_id,
            role=role,
            content=content,
            workspace_id=workspace_id,
            **kwargs
        )
        await self.conv_repo.update_message_count(conversation_id)

        # Auto-update title if it's a USER message and title is currently default/NULL
        if role == "USER":
            title = content[:100] + ("..." if len(content) > 100 else "")
            try:
                await self.conv_repo.update_title_if_default(conversation_id, title)
            except Exception as e:
                logger.error("failed_to_auto_update_conversation_title", error=str(e), conversation_id=str(conversation_id))

        return message


conversation_service = ConversationService()
