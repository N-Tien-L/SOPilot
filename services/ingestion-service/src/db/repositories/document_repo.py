from typing import Optional
from uuid import UUID
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.document import Document
from src.models.document_version import DocumentVersion


class DocumentRepository:
    """Repository for document database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, document_id: UUID) -> Optional[Document]:
        """Get document by ID."""
        result = await self.session.execute(
            select(Document).where(Document.id == document_id, Document.deleted_at == None)
        )
        return result.scalar_one_or_none()

    async def update_extracted_text(
        self, version_id: UUID, extracted_text: str, page_count: int, word_count: int
    ) -> None:
        """Update document version with extracted text and metadata."""
        await self.session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.id == version_id)
            .values(
                extracted_text=extracted_text,
            )
        )
        # Also update Document with counts if needed, but for now just text
        # Wait, if we want to update page_count/word_count on Document too:
        # (Document model doesn't have them yet, so we'll skip for now)
        pass

    async def update_status(self, document_id: UUID, status: str) -> None:
        """Update document processing status."""
        await self.session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=text("CAST(:status AS knowledge.processing_status)").bindparams(status=status))
        )
        await self.session.commit()

    async def update_ocr_confidence(self, document_id: UUID, ocr_confidence: float) -> None:
        """Update document OCR confidence after extraction."""
        await self.session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(ocr_confidence=ocr_confidence)
        )
