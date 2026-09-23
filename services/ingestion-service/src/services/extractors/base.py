"""Base extractor interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class ExtractedChunk:
    """A single extracted chunk with metadata."""
    content: str
    chunk_index: int
    chunk_type: str  # 'parent' or 'child'
    section_title: Optional[str] = None
    section_level: Optional[int] = None
    section_path: Optional[str] = None
    page_number: Optional[int] = None
    start_char_index: Optional[int] = None
    end_char_index: Optional[int] = None


@dataclass
class ExtractedDocument:
    """Full document extraction result."""
    text: str
    chunks: list[ExtractedChunk]
    page_count: int
    language: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DocumentExtractor(ABC):
    """Abstract base class for format-specific document extractors."""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        pass

    @abstractmethod
    async def extract(
        self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        """Extract text and chunks from file bytes."""
        pass