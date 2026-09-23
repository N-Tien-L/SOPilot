"""Ingestion pipeline - coordinates all processing steps."""

import hashlib
import time
from uuid import UUID

import structlog

from src.services.minio_service import minio_service
from src.services.extractors.orchestrator import orchestrator
from src.services.standardizer import DocumentPolicyStandardizer
from src.services.chunker import ParentChildChunker
from src.services.embedding_service import embedding_service
from src.services.processing_job_service import processing_job_service
from src.services.deduplicator import deduplicator
from src.db.repositories.chunk_repo import ChunkRepository
from src.db.repositories.version_repo import VersionRepository
from src.db.repositories.document_repo import DocumentRepository
from src.db.repositories.job_repo import JobRepository
from src.db.session import async_session
from src.models.extraction import Chunk
from src.models.document import Document

logger = structlog.get_logger()


def _log_stage(
    *,
    stage: str,
    duration_ms: float,
    document_id: UUID,
    version_id: UUID,
    job_id: UUID | None,
    extra: dict | None = None,
) -> None:
    """Emit one structured event per pipeline stage with timing context."""
    payload = {
        "stage": stage,
        "duration_ms": round(duration_ms, 3),
        "document_id": str(document_id),
        "version_id": str(version_id),
        "job_id": str(job_id) if job_id else None,
    }
    if extra:
        payload.update(extra)
    logger.info("pipeline_stage_completed", **payload)


class IngestionPipeline:
    """Coordinates the full document ingestion pipeline."""

    def __init__(self):
        self.standardizer = DocumentPolicyStandardizer()
        self.chunker = ParentChildChunker()

    async def process(
        self,
        document_id: UUID,
        version_id: UUID,
        job_id: UUID,
        bucket_name: str,
        file_key: str,
        metadata: dict,
        document_version: int = 1,
    ) -> dict:
        """Run the full ingestion pipeline."""
        logger.info(
            "pipeline_started",
            document_id=document_id,
            version_id=version_id,
            job_id=job_id,
            file_key=file_key,
        )

        pipeline_start = time.perf_counter()

        logger.info(
            "pipeline_input_received",
            document_id=document_id,
            version_id=version_id,
            job_id=job_id,
            file_key=file_key,
            bucket_name=bucket_name,
            document_version=document_version,
            metadata_keys=sorted(list(metadata.keys())) if metadata else [],
        )

        try:
            # --- 0. VALIDATION ---
            ALLOWED_BUCKETS = ["poliwise-documents"]
            if bucket_name not in ALLOWED_BUCKETS:
                raise ValueError(f"Unauthorized bucket access: {bucket_name}")

            # --- 1. DOWNLOAD ---
            await processing_job_service.update_progress(job_id, 10, "Layer 1: Checking file checksum")

            download_start = time.perf_counter()
            file_bytes = await minio_service.download_file(bucket_name, file_key)
            _log_stage(
                stage="download",
                duration_ms=(time.perf_counter() - download_start) * 1000,
                document_id=document_id,
                version_id=version_id,
                job_id=job_id,
                extra={
                    "bucket_name": bucket_name,
                    "file_key": file_key,
                    "file_size_bytes": len(file_bytes) if file_bytes is not None else 0,
                },
            )

            # Layer 1: Exact File Checksum
            dup_file = await deduplicator.check_file_duplicate(file_bytes, exclude_version_id=version_id)

            if dup_file.is_duplicate:
                return await self._handle_duplicate(
                    job_id, document_id, version_id, dup_file,
                    layer="L1_file_checksum",
                    duration_ms=(time.perf_counter() - pipeline_start) * 1000,
                )

            file_checksum = hashlib.sha256(file_bytes).hexdigest()

            # --- 2. EXTRACTION ---
            await processing_job_service.update_progress(job_id, 30, "Extracting text content")

            extract_start = time.perf_counter()
            extracted = await orchestrator.extract(file_bytes, file_key, document_id, version_id)
            _log_stage(
                stage="extract",
                duration_ms=(time.perf_counter() - extract_start) * 1000,
                document_id=document_id,
                version_id=version_id,
                job_id=job_id,
                extra={
                    "page_count": getattr(extracted, "page_count", None),
                    "text_len": len(extracted.text) if extracted.text else 0,
                    "file_size_bytes": len(file_bytes) if file_bytes is not None else 0,
                },
            )

            # Layer 2: Exact Content Hash
            dup_content = await deduplicator.check_content_duplicate(extracted.text)
            if dup_content.is_duplicate:
                return await self._handle_duplicate(
                    job_id, document_id, version_id, dup_content,
                    layer="L2_content_hash",
                    duration_ms=(time.perf_counter() - pipeline_start) * 1000,
                )

            content_hash = hashlib.sha256(extracted.text.encode("utf-8")).hexdigest()

            # --- 3. LAYER 3 SEMANTIC DEDUPLICATION (FINGERPRINT) ---
            await processing_job_service.update_progress(job_id, 60, "Layer 3: Checking semantic similarity")

            # Layer 3: Near-duplicate detection (Semantic Fingerprint)
            dup_semantic = await deduplicator.check_semantic_duplicate(extracted.text)
            if dup_semantic.is_duplicate:
                return await self._handle_duplicate(
                    job_id, document_id, version_id, dup_semantic,
                    layer="L3_semantic",
                    duration_ms=(time.perf_counter() - pipeline_start) * 1000,
                )

            # Track near-duplicate info for job metrics
            near_duplicate_info = None
            if dup_semantic.should_suggest_version and dup_semantic.existing_version_id:
                near_duplicate_info = {
                    "existing_version_id": str(dup_semantic.existing_version_id),
                    "similarity": dup_semantic.similarity,
                    "method": dup_semantic.method
                }
                # Keep legacy event for backward compatibility
                logger.info(
                    "near_duplicate_detected",
                    existing_version_id=str(dup_semantic.existing_version_id),
                    similarity=dup_semantic.similarity,
                )

            # Log a single summary line so we can grep "passed all dedup layers"
            logger.info(
                "pipeline_dedup_passed_all_layers",
                document_id=document_id,
                version_id=version_id,
                job_id=job_id,
                file_checksum=file_checksum,
                content_hash=content_hash,
                text_len=len(extracted.text) if extracted.text else 0,
                top_similarity=dup_semantic.similarity,
                near_duplicate_suggested=bool(near_duplicate_info),
            )

            # --- 4. STANDARDIZATION & CHUNKING ---
            await processing_job_service.update_progress(job_id, 70, "Standardizing text and chunking")

            chunk_start = time.perf_counter()
            structured = self.standardizer.normalize(extracted.text)

            # Prepare metadata for chunker - convert UUIDs to strings for JSON serialization
            chunk_metadata = {
                "document_id": str(document_id),
                "document_version_id": str(version_id),
                "document_version": document_version,
                "allowed_roles": metadata.get("allowed_roles"),
                "allowed_departments": metadata.get("allowed_departments"),
                "allowed_users": metadata.get("allowed_users"),
                "access_level": metadata.get("access_level", "RESTRICTED"),
                "department_id": metadata.get("department_id"),
                "document_type": metadata.get("document_type"),
                "effective_date": metadata.get("effective_date"),
                "expiry_date": metadata.get("expiry_date"),
            }

            chunks = self.chunker.chunk(structured, chunk_metadata)
            _log_stage(
                stage="chunk",
                duration_ms=(time.perf_counter() - chunk_start) * 1000,
                document_id=document_id,
                version_id=version_id,
                job_id=job_id,
                extra={"chunk_count": len(chunks) if chunks else 0},
            )

            # --- 5. EMBEDDING (in batches to avoid payload size limits) ---
            await processing_job_service.update_progress(job_id, 80, "Generating embeddings (BGE-M3)")

            # BGE-M3 has max-batch-tokens=16384, and embed_batch truncates each text to 512 tokens
            # Max safe batch size: 16384 / 512 = 32 chunks per batch
            EMBED_BATCH_SIZE = 32
            embed_start = time.perf_counter()
            embed_batch_count = 0
            embed_total_items = 0

            async with async_session() as session:
                chunk_contents = [c.content for c in chunks]
                embeddings = [None] * len(chunk_contents)

                # Process embeddings in batches
                for batch_start in range(0, len(chunk_contents), EMBED_BATCH_SIZE):
                    batch_end = min(batch_start + EMBED_BATCH_SIZE, len(chunk_contents))
                    batch_texts = chunk_contents[batch_start:batch_end]

                    batch_embeddings = await embedding_service.embed_batch_cached(batch_texts, session)

                    for i, emb in enumerate(batch_embeddings):
                        embeddings[batch_start + i] = emb
                    embed_batch_count += 1
                    embed_total_items += len(batch_texts)

                for i, emb in enumerate(embeddings):
                    chunks[i].embedding_vector = emb
                    chunks[i].embedding_model = "BGE_M3"
                    chunks[i].embedding_dimension = 1024

                _log_stage(
                    stage="embed",
                    duration_ms=(time.perf_counter() - embed_start) * 1000,
                    document_id=document_id,
                    version_id=version_id,
                    job_id=job_id,
                    extra={
                        "batch_count": embed_batch_count,
                        "total_items": embed_total_items,
                        "embedding_model": "BGE_M3",
                        "embedding_dim": 1024,
                    },
                )

                # --- 6. PERSISTENCE ---
                await processing_job_service.update_progress(job_id, 90, "Saving results to database")

                persist_start = time.perf_counter()
                ver_repo = VersionRepository(session)

                # Compute similarity to previous version if fingerprint exists
                similarity_to_previous = None
                if dup_semantic.vector is not None:
                    prev_versions = await ver_repo.find_near_duplicates(
                        dup_semantic.vector, threshold=0.0, limit=1
                    )
                    if prev_versions:
                        _, sim = prev_versions[0]
                        similarity_to_previous = sim

                # Save Version Metadata (checksums, fingerprint, similarity)
                await ver_repo.update_version(
                    version_id,
                    file_checksum=file_checksum,
                    content_hash=content_hash,
                    fingerprint_embedding=dup_semantic.vector,
                    similarity_to_previous=similarity_to_previous,
                )

                # Save Extracted Text to DocumentVersion
                doc_repo = DocumentRepository(session)
                await doc_repo.update_extracted_text(
                    version_id,
                    extracted_text=extracted.text,
                    page_count=extracted.page_count,
                    word_count=len(extracted.text.split())
                )

                # Save OCR confidence if available from extraction metadata
                ocr_conf = extracted.metadata.get("ocr_confidence")
                if ocr_conf is not None:
                    await doc_repo.update_ocr_confidence(document_id, ocr_conf)

                # Bulk Insert Chunks
                chunk_repo = ChunkRepository(session)
                # First mark old chunks as not latest
                await chunk_repo.mark_not_latest(document_id)
                await chunk_repo.bulk_insert(chunks)

                # Update Document status to READY
                await doc_repo.update_status(document_id, "READY")
                await session.commit()

                _log_stage(
                    stage="persist",
                    duration_ms=(time.perf_counter() - persist_start) * 1000,
                    document_id=document_id,
                    version_id=version_id,
                    job_id=job_id,
                    extra={"chunk_count": len(chunks) if chunks else 0},
                )

            # --- COMPLETE JOB ---
            await processing_job_service.complete_job(job_id, True, {
                "page_count": extracted.page_count,
                "method": "extraction_success",
                "semantic_similarity": dup_semantic.similarity if dup_semantic.is_duplicate else None,
                "deduplication_passed": True,
                "near_duplicate": near_duplicate_info,
                "chunk_count": len(chunks)
            })

            total_duration_ms = (time.perf_counter() - pipeline_start) * 1000
            logger.info(
                "pipeline_completed",
                document_id=document_id,
                version_id=version_id,
                job_id=job_id,
                total_duration_ms=round(total_duration_ms, 3),
                chunk_count=len(chunks),
            )

            return {
                "status": "completed",
                "document_id": str(document_id),
                "version_id": str(version_id)
            }

        except Exception as e:
            logger.error(
                "pipeline_failed",
                document_id=document_id,
                version_id=version_id,
                job_id=job_id,
                total_duration_ms=round((time.perf_counter() - pipeline_start) * 1000, 3),
                error=str(e),
                exc_info=True,
            )
            # Update status to FAILED
            try:
                async with async_session() as session:
                    doc_repo = DocumentRepository(session)
                    await doc_repo.update_status(document_id, "FAILED")

                    job_repo = JobRepository(session)
                    if job_id:
                        await job_repo.mark_failed(job_id, str(e))
            except Exception as inner_e:
                logger.error(f"Failed to record failure state: {inner_e}")

            return {"status": "FAILED", "error": str(e)}

    async def _handle_duplicate(
        self,
        job_id: UUID,
        document_id: UUID,
        version_id: UUID,
        result,
        *,
        layer: str | None = None,
        duration_ms: float | None = None,
    ) -> dict:
        """Helper to handle duplicate detection hits.

        Extra kwargs (layer, duration_ms) add debug context to the
        deduplication_hit event without breaking existing callers/tests.
        """
        logger.info(
            "deduplication_hit",
            method=result.method,
            duplicate_of=str(result.existing_version_id),
            layer=layer,
            document_id=document_id,
            version_id=version_id,
            job_id=job_id,
            total_duration_ms=round(duration_ms, 3) if duration_ms is not None else None,
            similarity=result.similarity,
        )

        async with async_session() as session:
            doc_repo = DocumentRepository(session)
            # Set to DUPLICATE since content is available via the duplicate
            await doc_repo.update_status(document_id, "DUPLICATE")

        await processing_job_service.complete_job(job_id, True, {
            "duplicate_of": str(result.existing_version_id),
            "method": result.method,
            "similarity": result.similarity,
            "skipped": True,
        })

        return {
            "status": "skipped",
            "reason": "duplicate",
            "method": result.method,
            "existing_version": str(result.existing_version_id),
        }


pipeline = IngestionPipeline()
