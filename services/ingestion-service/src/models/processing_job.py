import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, BigInteger, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from src.db.session import Base


class ProcessingJob(Base):
    """SQLAlchemy model for knowledge.processing_jobs table."""
    __tablename__ = "processing_jobs"
    __table_args__ = {"schema": "knowledge"}

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(PG_UUID(as_uuid=True), nullable=False)
    document_version_id = Column(PG_UUID(as_uuid=True), nullable=True)
    job_type = Column(String(50), nullable=False)  # 'INGESTION' or 'REINDEX'
    status = Column(String(50), nullable=False)  # 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    progress_percent = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)
    error_details = Column(JSONB, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    output_metrics = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
