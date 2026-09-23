import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from src.db.session import Base


class Document(Base):
    """SQLAlchemy model for knowledge.documents table."""
    __tablename__ = "documents"
    __table_args__ = {"schema": "knowledge"}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(255), nullable=False)
    file_key = Column(String(500), nullable=False)
    bucket_name = Column(String(255), nullable=False, default='poliwise-documents')
    status = Column(String(50), default='PENDING')
    current_version = Column(Integer, default=1)
    extracted_text = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    language = Column(String(10), default='en')
    domain = Column(String(50), nullable=True)
    content_quality = Column(String(50), nullable=True)
    ocr_required = Column(Boolean, default=False)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    chunking_strategy = Column(String(50), default='parent_child')
    chunk_size = Column(Integer, nullable=True)
    chunk_overlap = Column(Integer, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    uploaded_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    trace_id = Column(String(100), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True, default=dict)
