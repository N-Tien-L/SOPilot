from typing import Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.document_version import DocumentVersion
from src.models.document import Document


class VersionRepository:
    """Repository for document version database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, version_id: UUID) -> Optional[DocumentVersion]:
        """Get document version by ID."""
        result = await self.session.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == version_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_not_current(self, document_id: UUID) -> None:
        """Mark all versions for a document as not current."""
        await self.session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.document_id == document_id, DocumentVersion.is_current == True)
            .values(is_current=False)
        )

    async def update_extracted_text(self, version_id: UUID, extracted_text: str) -> None:
        """Update version with extracted text."""
        await self.session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.id == version_id)
            .values(extracted_text=extracted_text)
        )

    async def update_version(
        self,
        version_id: UUID,
        extracted_text: Optional[str] = None,
        file_checksum: Optional[str] = None,
        content_hash: Optional[str] = None,
        fingerprint_embedding: Optional[list[float]] = None,
        similarity_to_previous: Optional[float] = None,
        page_count: Optional[int] = None,
        language: Optional[str] = None,
    ) -> None:
        """Update version with extraction results and redundancy detection fields."""
        values = {}
        if extracted_text is not None:
            values["extracted_text"] = extracted_text
        if file_checksum is not None:
            values["file_checksum"] = file_checksum
        if content_hash is not None:
            values["content_hash"] = content_hash
        if fingerprint_embedding is not None:
            values["fingerprint_embedding"] = fingerprint_embedding
        if similarity_to_previous is not None:
            values["similarity_to_previous"] = similarity_to_previous
        # Note: page_count and language are not columns on document_versions table,
        # they are tracked on the documents table via knowledge-service.
        # We skip them here to avoid SQL errors.

        if values:
            await self.session.execute(
                update(DocumentVersion)
                .where(DocumentVersion.id == version_id)
                .values(**values)
            )
            await self.session.commit()

    async def find_by_file_checksum(self, file_checksum: str, exclude_version_id: UUID = None) -> Optional[DocumentVersion]:
        """Find version by file checksum for exact duplicate detection.
        Excludes versions from deleted documents and (optionally) a specific version id.
        """
        query = (
            select(DocumentVersion)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentVersion.file_checksum == file_checksum,
                Document.deleted_at == None
            )
        )
        if exclude_version_id:
            query = query.where(DocumentVersion.id != exclude_version_id)
        query = query.order_by(DocumentVersion.created_at.desc()).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_content_hash(self, content_hash: str, exclude_version_id: UUID = None) -> list[DocumentVersion]:
        """Find versions with same content hash (for deduplication).
        Excludes versions from deleted documents.
        """
        query = (
            select(DocumentVersion)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentVersion.content_hash == content_hash,
                Document.deleted_at == None
            )
        )
        if exclude_version_id:
            query = query.where(DocumentVersion.id != exclude_version_id)
        result = await self.session.execute(query.limit(10))
        return list(result.scalars().all())

    async def find_near_duplicates(
        self,
        embedding: list[float],
        threshold: float = 0.90,
        limit: int = 5
    ) -> list[tuple[DocumentVersion, float]]:
        """Find versions with high semantic similarity using vector distance.
        The embedding should be a 'Semantic Fingerprint' (multi-sample weighted average).
        Excludes versions from deleted documents.
        """
        # pgvector uses <=> for cosine distance (1 - similarity)
        # So similarity = 1 - (embedding_vector <=> :embedding)
        # We want similarity > threshold  =>  distance < 1 - threshold
        distance_threshold = 1.0 - threshold

        query = (
            select(
                DocumentVersion,
                DocumentVersion.fingerprint_embedding.cosine_distance(embedding).label("distance")
            )
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentVersion.fingerprint_embedding.cosine_distance(embedding) < distance_threshold,
                Document.deleted_at == None
            )
            .order_by("distance")
            .limit(limit)
        )

        result = await self.session.execute(query)
        results = [(row[0], 1.0 - float(row[1])) for row in result.all()]

        return results