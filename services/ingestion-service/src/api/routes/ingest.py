from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_session
from src.services.pipeline import pipeline
from src.db.repositories.job_repo import JobRepository
from src.db.repositories.version_repo import VersionRepository
from src.db.repositories.document_repo import DocumentRepository
from src.api.dependencies import get_api_key
from src.db.session import async_session

router = APIRouter()
logger = structlog.get_logger()


class IngestRequest(BaseModel):
    """Request payload for manual ingestion."""
    document_id: UUID
    document_version_id: UUID
    document_version: int
    file_key: str
    bucket_name: str
    job_id: UUID
    metadata: Optional[dict] = None


class IngestResponse(BaseModel):
    """Response for ingestion request."""
    job_id: UUID
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status query."""
    job_id: UUID
    status: str
    progress_percent: Optional[int] = None
    error_message: Optional[str] = None


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(get_api_key)])
async def ingest_document(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger ingestion for a document.
    Runs in the background task to not block the request.
    """
    logger.info("manual_ingest_requested", job_id=str(request.job_id))
    
    # Start the pipeline in background
    background_tasks.add_task(
        pipeline.process,
        document_id=request.document_id,
        version_id=request.document_version_id,
        document_version=request.document_version,
        job_id=request.job_id,
        bucket_name=request.bucket_name,
        file_key=request.file_key,
        metadata=request.metadata or {}
    )

    return IngestResponse(
        job_id=request.job_id,
        status="processing",
        message="Ingestion job started in background",
    )


@router.get("/ingest/{job_id}/status", response_model=JobStatusResponse, dependencies=[Depends(get_api_key)])
async def get_ingestion_status(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Get current status and progress of an ingestion job.
    """
    repo = JobRepository(session)
    job = await repo.get_by_id(job_id)
    
    if not job:
        raise HTTPException(status_status=404, detail="Job not found")
        
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress_percent=job.progress_percent,
        error_message=job.error_message
    )


# ===== Duplicate Check Endpoints =====

class DuplicateCheckResponse(BaseModel):
    """Response for duplicate check."""
    is_duplicate: bool
    action: Optional[str] = None  # "BLOCK" | "SUGGEST_VERSION" | null
    existing_document: Optional[dict] = None
    similarity: Optional[float] = None
    detection_method: Optional[str] = None


class JobStatusDetailResponse(BaseModel):
    """Detailed response for job status query with output metrics."""
    job_id: UUID
    status: str
    progress_percent: Optional[int] = None
    output_metrics: Optional[dict] = None
    error_message: Optional[str] = None


@router.get("/check-duplicate", response_model=DuplicateCheckResponse)
async def check_duplicate(
    checksum: str,
):
    """
    Check if a file with the given SHA-256 checksum is a duplicate.
    This is the Layer 1 (file checksum) check endpoint.
    """
    async with async_session() as session:
        repo = VersionRepository(session)
        existing = await repo.find_by_file_checksum(checksum)

        if existing:
            logger.info("duplicate_check_hit", method="file_checksum", version_id=str(existing.id))
            # DocumentVersion does not have original_filename/file_size_bytes.
            # Fetch the parent Document to expose those fields to callers.
            doc_repo = DocumentRepository(session)
            parent_doc = await doc_repo.get_by_id(existing.document_id)
            return DuplicateCheckResponse(
                is_duplicate=True,
                action="BLOCK",
                existing_document={
                    "document_id": str(existing.document_id),
                    "original_filename": parent_doc.original_filename if parent_doc else None,
                    "file_size_bytes": existing.file_size_bytes,
                    "file_checksum": existing.file_checksum,
                    "version_number": existing.version_number,
                },
                detection_method="file_checksum"
            )

    return DuplicateCheckResponse(
        is_duplicate=False,
        action=None,
        existing_document=None,
        similarity=None,
        detection_method=None
    )


@router.get("/jobs/{job_id}", response_model=JobStatusDetailResponse)
async def get_job_status(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed status of a processing job including output metrics.
    Used for polling during sync confirm flow.
    """
    repo = JobRepository(session)
    job = await repo.get_by_id(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Parse output_metrics if it's a JSON string
    output_metrics = None
    if job.output_metrics:
        import json
        try:
            output_metrics = json.loads(job.output_metrics)
        except Exception:
            output_metrics = {"raw": job.output_metrics}
    
    return JobStatusDetailResponse(
        job_id=job.id,
        status=job.status,
        progress_percent=job.progress_percent,
        output_metrics=output_metrics,
        error_message=job.error_message
    )
