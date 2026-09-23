import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector
from src.db.session import Base


class EmbeddingCache(Base):
    """SQLAlchemy model for knowledge.embedding_cache table.

    Caches embedding vectors keyed by a SHA-256 hash of the chunk text.
    When the same text appears in a future ingestion run (e.g. a document
    version where only a few paragraphs changed), the cached vector is
    reused instead of calling the embedding API again.
    """
    __tablename__ = "embedding_cache"
    __table_args__ = (
        UniqueConstraint('text_hash', 'embedding_model', name='uq_embedding_cache'),
        {"schema": "knowledge"}
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text_hash = Column(String(64), nullable=False)          # SHA-256 hex digest
    text_length = Column(Integer, nullable=False)
    embedding_model = Column(String(100), nullable=False)   # e.g. "bge-m3"
    embedding_dimension = Column(Integer, nullable=False)    # e.g. 1024
    embedding_vector = Column(Vector(1024), nullable=False)
    usage_count = Column(Integer, default=1, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
