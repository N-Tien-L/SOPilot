from uuid import UUID
from src.db.session import async_session
from src.db.repositories.job_repo import JobRepository


class ProcessingJobService:
    """Service for managing processing job status updates."""

    async def update_progress(self, job_id: UUID, percent: int, message: str | None = None) -> None:
        """Update job progress percentage and status message."""
        async with async_session() as session:
            repo = JobRepository(session)
            # Use PARSING (matches knowledge.processing_status enum). The job moves
            # through PARSING → CHUNKING → EMBEDDING → INDEXING as it advances.
            await repo.update_status(
                job_id,
                "PARSING",
                progress_percent=percent,
                error_message=message
            )
            await session.commit()

    async def mark_processing(self, job_id: UUID) -> None:
        """Mark job as processing started."""
        async with async_session() as session:
            repo = JobRepository(session)
            await repo.update_status(job_id, "PARSING", progress_percent=0)
            await session.commit()

    async def complete_job(self, job_id: UUID, success: bool, metrics: dict | None = None, error_message: str | None = None) -> None:
        """Complete job with success or failure status."""
        if success:
            await self.mark_completed(job_id, metrics or {})
        else:
            await self.mark_failed(job_id, error_message or "Unknown error")

    async def mark_completed(self, job_id: UUID, metrics: dict) -> None:
        """Mark job as completed with output metrics."""
        import json
        async with async_session() as session:
            repo = JobRepository(session)
            await repo.mark_completed(job_id, output_metrics=json.dumps(metrics))
            await session.commit()

    async def mark_failed(self, job_id: UUID, error_message: str, error_details: str | None = None) -> None:
        """Mark job as failed with error information."""
        async with async_session() as session:
            repo = JobRepository(session)
            await repo.mark_failed(job_id, error_message, error_details)
            await session.commit()


# Global service instance
processing_job_service = ProcessingJobService()
