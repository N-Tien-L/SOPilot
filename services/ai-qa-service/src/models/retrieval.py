from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional, List


class RetrievalChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    document_id: UUID
    document_name: Optional[str] = None
    content: str
    section_title: Optional[str] = None
    similarity_score: float
    start_char_index: Optional[int] = None
    end_char_index: Optional[int] = None
    metadata: Optional[dict] = None


class RetrievalFilters(BaseModel):
    document_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class RetrievalResult(BaseModel):
    chunks: List[RetrievalChunk]
    query: str
    total_results: int