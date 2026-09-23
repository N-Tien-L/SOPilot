import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Text, BigInteger, Integer, Boolean, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from pgvector.sqlalchemy import Vector
from src.db.session import Base


class Chunk(Base):
    """SQLAlchemy model for knowledge.chunks table."""
    __tablename__ = "chunks"
    __table_args__ = {"schema": "knowledge"}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(PG_UUID(as_uuid=True), nullable=False)
    document_version_id = Column(PG_UUID(as_uuid=True), nullable=True)
    document_version = Column(Integer, nullable=False)
    chunk_type = Column(String, nullable=False)  # "parent" or "child"
    parent_chunk_id = Column(PG_UUID(as_uuid=True), nullable=True)
    content = Column(Text, nullable=False)
    content_length = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_title = Column(String, nullable=True)
    section_level = Column(Integer, nullable=True)
    section_path = Column(ARRAY(String), nullable=True)
    bucket_name = Column(String(100), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    start_char_index = Column(Integer, nullable=True)
    end_char_index = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_dimension = Column(Integer, nullable=True)
    vector_indexed = Column(Boolean, default=False)
    vector_id = Column(String(100), nullable=True)
    embedding_vector = Column(Vector(1024), nullable=True)  # BGE-M3: 1024-dim
    department_id = Column(PG_UUID(as_uuid=True), nullable=True)
    document_type = Column(String(50), nullable=True)
    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    allowed_roles = Column(ARRAY(String), nullable=True)
    allowed_departments = Column(ARRAY(PG_UUID(as_uuid=True)), nullable=True)
    allowed_users = Column(ARRAY(PG_UUID(as_uuid=True)), nullable=True)
    access_level = Column(String, nullable=False, default="RESTRICTED")
    is_latest = Column(Boolean, default=True, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)  # metadata column
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
