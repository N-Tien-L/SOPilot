from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class ExtractedDocument:
    """Represents a document after extraction."""
    document_id: UUID
    version_id: UUID
    raw_text: str
    page_count: int = 0
    word_count: int = 0
    metadata: dict = field(default_factory=dict)
    headings: list[dict] = field(default_factory=list)


@dataclass
class StructuredText:
    """Text with detected structure (headings, sections)."""
    normalized_text: str
    headings: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)


@dataclass
class Chunk:
    """Represents a chunk ready for embedding."""
    document_id: UUID
    document_version_id: UUID
    document_version: int
    chunk_type: str  # "parent" or "child"
    content: str
    chunk_id: Optional[UUID] = None
    section_title: Optional[str] = None
    section_level: Optional[int] = None
    section_path: Optional[list[str]] = None
    chunk_index: int = 0
    start_char_index: int = 0
    end_char_index: int = 0
    token_count: int = 0
    embedding_vector: Optional[list[float]] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    parent_chunk_id: Optional[UUID] = None
    allowed_roles: Optional[list[str]] = None
    allowed_departments: Optional[list[str]] = None
    allowed_users: Optional[list[str]] = None
    access_level: str = "RESTRICTED"
    department_id: Optional[str] = None
    document_type: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    metadata: dict = field(default_factory=dict)
