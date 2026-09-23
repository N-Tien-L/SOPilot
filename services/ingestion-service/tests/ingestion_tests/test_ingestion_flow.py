"""
Integration-style tests for the ingestion pipeline.

These tests mock external dependencies (MinIO, DB, embedding service) so they
run fast without needing a real database or MinIO instance. Each test uses
unique UUIDs and mocks to avoid deduplication conflicts between runs.

Run with:
    cd services/ingestion-service
    python -m pytest tests/ingestion_tests/test_ingestion_flow.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from src.services.pipeline import IngestionPipeline
from src.services.deduplicator import DeduplicationResult
from src.services.extractors.base import ExtractedDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dedup_result(is_duplicate: bool, method: str = None, **kwargs) -> DeduplicationResult:
    """Build a DeduplicationResult with sensible defaults."""
    return DeduplicationResult(
        is_duplicate=is_duplicate,
        existing_version_id=kwargs.get("existing_version_id", uuid4() if is_duplicate else None),
        method=method if is_duplicate else None,
        similarity=kwargs.get("similarity"),
        vector=kwargs.get("vector"),
    )


def _make_extracted_doc(text: str = "Test content", chunks: list = None, page_count: int = 1) -> ExtractedDocument:
    """Build an ExtractedDocument with sensible defaults."""
    return ExtractedDocument(
        text=text,
        chunks=chunks or [],
        page_count=page_count,
        language="en",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline():
    """Fresh pipeline instance for each test."""
    return IngestionPipeline()


@pytest.fixture
def mock_session():
    """Mock async DB session that supports async context manager."""
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


@pytest.fixture
def base_params():
    """Return a dict of base parameters for pipeline.process()."""
    return {
        "document_id": uuid4(),
        "version_id": uuid4(),
        "document_version": 1,
        "job_id": uuid4(),
        "bucket_name": "poliwise-documents",
        "file_key": "test/file.pdf",
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Layer 1 – File Checksum Duplicate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_layer1_file_checksum_duplicate(pipeline, base_params):
    """
    Layer 1: when the file bytes match an existing file checksum,
    the pipeline should skip processing and return status='skipped'.
    """
    # _handle_duplicate uses async_session from pipeline's own namespace,
    # NOT from src.db.session — so patch the pipeline-local reference.
    with patch(
        "src.services.pipeline.async_session", return_value=AsyncMock()
    ), patch(
        "src.services.minio_service.minio_service.download_file", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.services.deduplicator.deduplicator.check_file_duplicate", new_callable=AsyncMock
    ) as mock_check_file, patch(
        "src.services.processing_job_service.processing_job_service.complete_job", new_callable=AsyncMock
    ) as mock_complete, patch(
        "src.services.processing_job_service.processing_job_service.update_progress", new_callable=AsyncMock
    ):

        mock_download.return_value = b"identical_bytes"
        mock_check_file.return_value = _make_dedup_result(is_duplicate=True, method="file_checksum")

        result = await pipeline.process(**base_params)

        assert result["status"] == "skipped"
        assert result["method"] == "file_checksum"
        mock_check_file.assert_called_once()
        mock_complete.assert_called_once()


# ---------------------------------------------------------------------------
# Layer 2 – Content Hash Duplicate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_layer2_content_hash_duplicate(pipeline, base_params):
    """
    Layer 2: when extracted text matches an existing content hash,
    the pipeline should skip and return status='skipped'.
    """
    # _handle_duplicate uses async_session from pipeline's own namespace
    with patch(
        "src.services.pipeline.async_session", return_value=AsyncMock()
    ), patch(
        "src.services.minio_service.minio_service.download_file", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.services.deduplicator.deduplicator.check_file_duplicate", new_callable=AsyncMock
    ) as mock_check_file, patch(
        "src.services.extractors.orchestrator.orchestrator.extract", new_callable=AsyncMock
    ) as mock_extract, patch(
        "src.services.deduplicator.deduplicator.check_content_duplicate", new_callable=AsyncMock
    ) as mock_check_content, patch(
        "src.services.processing_job_service.processing_job_service.complete_job", new_callable=AsyncMock
    ) as mock_complete, patch(
        "src.services.processing_job_service.processing_job_service.update_progress", new_callable=AsyncMock
    ):

        mock_download.return_value = b"different_bytes"
        mock_check_file.return_value = _make_dedup_result(is_duplicate=False)
        mock_extract.return_value = _make_extracted_doc(text="Duplicate content")
        mock_check_content.return_value = _make_dedup_result(is_duplicate=True, method="content_hash")

        result = await pipeline.process(**base_params)

        assert result["status"] == "skipped"
        assert result["method"] == "content_hash"
        mock_check_content.assert_called_once()
        mock_complete.assert_called_once()


# ---------------------------------------------------------------------------
# Layer 3 – Semantic Duplicate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_layer3_semantic_duplicate(pipeline, base_params):
    """
    Layer 3: when the semantic fingerprint matches an existing document,
    the pipeline should skip and return status='skipped'.
    """
    # _handle_duplicate uses async_session from pipeline's own namespace
    with patch(
        "src.services.pipeline.async_session", return_value=AsyncMock()
    ), patch(
        "src.services.minio_service.minio_service.download_file", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.services.deduplicator.deduplicator.check_file_duplicate", new_callable=AsyncMock
    ) as mock_check_file, patch(
        "src.services.extractors.orchestrator.orchestrator.extract", new_callable=AsyncMock
    ) as mock_extract, patch(
        "src.services.deduplicator.deduplicator.check_content_duplicate", new_callable=AsyncMock
    ) as mock_check_content, patch(
        "src.services.deduplicator.deduplicator.check_semantic_duplicate", new_callable=AsyncMock
    ) as mock_check_semantic, patch(
        "src.services.processing_job_service.processing_job_service.complete_job", new_callable=AsyncMock
    ) as mock_complete, patch(
        "src.services.processing_job_service.processing_job_service.update_progress", new_callable=AsyncMock
    ):

        mock_download.return_value = b"new_bytes"
        mock_check_file.return_value = _make_dedup_result(is_duplicate=False)
        mock_extract.return_value = _make_extracted_doc(text="Similar but not identical content")
        mock_check_content.return_value = _make_dedup_result(is_duplicate=False)
        mock_check_semantic.return_value = _make_dedup_result(
            is_duplicate=True, method="semantic", similarity=0.99
        )

        result = await pipeline.process(**base_params)

        assert result["status"] == "skipped"
        assert result["method"] == "semantic"
        mock_check_semantic.assert_called_once()
        mock_complete.assert_called_once()


# ---------------------------------------------------------------------------
# Full Success Path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_success_path(pipeline, base_params, mock_session):
    """
    Happy path: no duplicates detected, full ingestion completes successfully.
    Verifies that chunks are saved, version is updated, and job is completed.
    """
    mock_factory = MagicMock(return_value=mock_session)

    with patch(
        "src.services.pipeline.async_session", mock_factory
    ), patch(
        "src.services.minio_service.minio_service.download_file", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.services.deduplicator.deduplicator.check_file_duplicate", new_callable=AsyncMock
    ) as mock_check_file, patch(
        "src.services.extractors.orchestrator.orchestrator.extract", new_callable=AsyncMock
    ) as mock_extract, patch(
        "src.services.deduplicator.deduplicator.check_content_duplicate", new_callable=AsyncMock
    ) as mock_check_content, patch(
        "src.services.deduplicator.deduplicator.check_semantic_duplicate", new_callable=AsyncMock
    ) as mock_check_semantic, patch(
        "src.services.embedding_service.embedding_service.embed_batch_cached", new_callable=AsyncMock
    ) as mock_embed, patch(
        "src.db.repositories.chunk_repo.ChunkRepository.bulk_insert", new_callable=AsyncMock
    ) as mock_chunk_save, patch(
        "src.db.repositories.version_repo.VersionRepository.update_version", new_callable=AsyncMock
    ) as mock_ver_save, patch(
        "src.db.repositories.document_repo.DocumentRepository.update_extracted_text", new_callable=AsyncMock
    ), patch(
        "src.db.repositories.document_repo.DocumentRepository.update_status", new_callable=AsyncMock
    ), patch(
        "src.db.repositories.chunk_repo.ChunkRepository.mark_not_latest", new_callable=AsyncMock
    ), patch(
        "src.services.processing_job_service.processing_job_service.update_progress", new_callable=AsyncMock
    ), patch(
        "src.services.processing_job_service.processing_job_service.complete_job", new_callable=AsyncMock
    ) as mock_complete:

        mock_download.return_value = b"unique_file_bytes"
        mock_check_file.return_value = _make_dedup_result(is_duplicate=False)
        mock_extract.return_value = _make_extracted_doc(
            text="Unique document content for testing", page_count=3
        )
        mock_check_content.return_value = _make_dedup_result(is_duplicate=False)
        mock_check_semantic.return_value = _make_dedup_result(
            is_duplicate=False, vector=[0.1] * 1024
        )
        mock_embed.return_value = [[0.2] * 1024]

        result = await pipeline.process(**base_params)

        assert result["status"] == "completed"
        mock_chunk_save.assert_called_once()
        mock_ver_save.assert_called_once()
        mock_complete.assert_called_once()


# ---------------------------------------------------------------------------
# Invalid Bucket
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_bucket_rejected(pipeline, base_params):
    """
    The pipeline should reject buckets that are not in the allowed list.
    """
    params = {**base_params, "bucket_name": "evil-bucket"}

    with patch(
        "src.services.processing_job_service.processing_job_service.update_progress", new_callable=AsyncMock
    ):

        result = await pipeline.process(**params)

        assert result["status"] == "FAILED"
        assert "Unauthorized bucket" in result["error"]


# ---------------------------------------------------------------------------
# Hard-delete cleanup helper (callable from tests that need real DB access)
# ---------------------------------------------------------------------------

async def hard_delete_test_data(document_id: UUID, version_id: UUID, job_id: UUID):
    """
    Hard-delete test records from the database to prevent deduplication
    conflicts in subsequent test runs.

    This should be called in a fixture teardown or at the end of any test
    that writes real data to the database.

    NOTE: This uses raw SQL DELETEs because the repository classes do not
    expose delete methods.  Only use this in test teardown — never in
    production code.
    """
    from src.db.session import async_session
    from sqlalchemy import text

    async with async_session() as session:
        # Order matters: delete children (chunks) first, then versions,
        # then documents, then jobs.
        await session.execute(
            text("DELETE FROM knowledge.chunks WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        await session.execute(
            text("DELETE FROM knowledge.document_versions WHERE id = :ver_id"),
            {"ver_id": version_id},
        )
        await session.execute(
            text("DELETE FROM knowledge.documents WHERE id = :doc_id"),
            {"doc_id": document_id},
        )
        await session.execute(
            text("DELETE FROM knowledge.processing_jobs WHERE id = :job_id"),
            {"job_id": job_id},
        )
        await session.commit()
