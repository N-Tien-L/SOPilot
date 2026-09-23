from typing import Optional
from uuid import UUID
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.processing_job import ProcessingJob


class JobRepository:
    """Repository for processing job database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, job_id: UUID) -> Optional[ProcessingJob]:
        """Get processing job by ID."""
        result = await self.session.execute(
            select(ProcessingJob).where(
                ProcessingJob.id == job_id,
                ProcessingJob.deleted_at == None
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: UUID,
        status: str,
        progress_percent: Optional[int] = None,
        error_message: Optional[str] = None,
        error_details: Optional[str] = None,
        output_metrics: Optional[str] = None,
    ) -> None:
        """Update job status and related fields."""
        values = {}
        if progress_percent is not None:
            values["progress_percent"] = progress_percent
        if error_message is not None:
            values["error_message"] = error_message
        if error_details is not None:
            values["error_details"] = error_details
        if output_metrics is not None:
            values["output_metrics"] = output_metrics

        await self.session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(**values)
            .values(status=text("CAST(:status AS knowledge.processing_status)").bindparams(status=status))
        )

    async def mark_completed(self, job_id: UUID, output_metrics: Optional[str] = None) -> None:
        """Mark job as completed."""
        # Use READY to match knowledge.processing_status enum (not COMPLETED).
        await self.update_status(job_id, "READY", progress_percent=100, output_metrics=output_metrics)

    async def mark_failed(
        self, job_id: UUID, error_message: str, error_details: Optional[str] = None
    ) -> None:
        """Mark job as failed."""
        await self.update_status(
            job_id, "FAILED", error_message=error_message, error_details=error_details
        )
