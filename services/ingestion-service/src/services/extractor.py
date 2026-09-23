from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from src.models.extraction import ExtractedDocument


class DocumentExtractor(ABC):
    """Abstract base class for format-specific document extractors."""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.pdf', '.docx'])."""
        pass

    @abstractmethod
    async def extract(
        self, file_bytes: bytes, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        """Extract text and metadata from file bytes."""
        pass


class ExtractionOrchestrator:
    """Registry/Strategy pattern for format-specific extractors."""

    def __init__(self):
        self._extractors: dict[str, DocumentExtractor] = {}

    def register(self, extractor: DocumentExtractor) -> None:
        """Register an extractor for its supported extensions."""
        for ext in extractor.supported_extensions():
            self._extractors[ext] = extractor

    async def extract(
        self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        """Route to appropriate extractor based on file extension."""
        ext = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""
        extractor = self._extractors.get(ext)
        if not extractor:
            raise ValueError(f"No extractor for extension: .{ext}")
        return await extractor.extract(file_bytes, document_id, version_id)


# Global orchestrator instance
orchestrator = ExtractionOrchestrator()
