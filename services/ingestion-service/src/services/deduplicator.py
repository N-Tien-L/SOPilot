import hashlib
import time
from typing import NamedTuple, Optional
from uuid import UUID

import structlog

from src.db.session import async_session
from src.db.repositories.version_repo import VersionRepository
from src.services.embedding_service import embedding_service

logger = structlog.get_logger()

# Module-level helpers ---------------------------------------------------------

def _log_check(
    *,
    layer: str,
    method: str,
    duration_ms: float,
    outcome: str,                       # "hit" | "miss" | "skipped_empty"
    document_version_id: Optional[UUID] = None,
    exclude_version_id: Optional[UUID] = None,
    input_size_bytes: Optional[int] = None,
    input_text_len: Optional[int] = None,
    fingerprint_len: Optional[int] = None,
    embedding_dim: Optional[int] = None,
    candidates_returned: Optional[int] = None,
    similarity: Optional[float] = None,
    existing_version_id: Optional[UUID] = None,
    block_threshold: Optional[float] = None,
    version_threshold: Optional[float] = None,
    extra: Optional[dict] = None,
) -> None:
    """Emit a single structured event describing one dedup layer check.

    Older event names (deduplication_hit_layer1/2, deduplication_layer3_result,
    near_duplicate_detected) are still emitted elsewhere to keep existing
    log dashboards / alerts working. This event is the single source of
    debug-friendly context for the dedup pipeline.
    """
    payload = {
        "layer": layer,
        "method": method,
        "outcome": outcome,
        "duration_ms": round(duration_ms, 3),
        "document_version_id": str(document_version_id) if document_version_id else None,
        "exclude_version_id": str(exclude_version_id) if exclude_version_id else None,
        "input_size_bytes": input_size_bytes,
        "input_text_len": input_text_len,
        "fingerprint_len": fingerprint_len,
        "embedding_dim": embedding_dim,
        "candidates_returned": candidates_returned,
        "similarity": similarity,
        "existing_version_id": str(existing_version_id) if existing_version_id else None,
        "block_threshold": block_threshold,
        "version_threshold": version_threshold,
    }
    if extra:
        payload.update(extra)
    logger.info("deduplication_check", **payload)


class DeduplicationResult(NamedTuple):
    """Result of redundancy detection."""
    is_duplicate: bool
    should_suggest_version: bool = False
    existing_version_id: Optional[UUID] = None
    method: Optional[str] = None  # "file_checksum", "content_hash", "semantic"
    similarity: Optional[float] = None
    vector: Optional[list[float]] = None


class Deduplicator:
    """Service for hybrid three-layer redundancy detection."""

    SEMANTIC_BLOCK_THRESHOLD = 0.98
    SEMANTIC_VERSION_THRESHOLD = 0.85

    async def check_file_duplicate(self, file_bytes: bytes, exclude_version_id: UUID = None) -> DeduplicationResult:
        """
        Layer 1: Exact duplicate detection via file checksum (SHA256).
        Checks if the exact same file (byte-for-byte) has been uploaded before.
        Optionally excludes a specific version id (e.g. the version being processed).
        """
        start = time.perf_counter()
        file_checksum = hashlib.sha256(file_bytes).hexdigest()

        existing = None
        try:
            async with async_session() as session:
                repo = VersionRepository(session)
                existing = await repo.find_by_file_checksum(file_checksum, exclude_version_id=exclude_version_id)

            if existing:
                # Keep legacy event for backward compatibility with log dashboards
                logger.info("deduplication_hit_layer1", method="file_checksum", version_id=str(existing.id))
                _log_check(
                    layer="L1_file_checksum",
                    method="file_checksum",
                    duration_ms=(time.perf_counter() - start) * 1000,
                    outcome="hit",
                    exclude_version_id=exclude_version_id,
                    input_size_bytes=len(file_bytes),
                    existing_version_id=existing.id,
                    extra={"file_checksum": file_checksum},
                )
                return DeduplicationResult(
                    is_duplicate=True,
                    should_suggest_version=False,
                    existing_version_id=existing.id,
                    method="file_checksum"
                )

            _log_check(
                layer="L1_file_checksum",
                method="file_checksum",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="miss",
                exclude_version_id=exclude_version_id,
                input_size_bytes=len(file_bytes),
                extra={"file_checksum": file_checksum},
            )
        except Exception as exc:
            _log_check(
                layer="L1_file_checksum",
                method="file_checksum",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="error",
                exclude_version_id=exclude_version_id,
                input_size_bytes=len(file_bytes) if file_bytes is not None else 0,
                extra={"file_checksum": file_checksum, "error": str(exc)},
            )
            raise

        return DeduplicationResult(is_duplicate=False, should_suggest_version=False)

    async def check_content_duplicate(self, extracted_text: str, exclude_version_id: UUID = None) -> DeduplicationResult:
        """
        Layer 2: Exact content detection via extracted text hash.
        Handles cases where the same text is inside different file formats (e.g. PDF vs Docx).
        """
        start = time.perf_counter()

        if not extracted_text:
            _log_check(
                layer="L2_content_hash",
                method="content_hash",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="skipped_empty",
                exclude_version_id=exclude_version_id,
                input_text_len=0,
            )
            return DeduplicationResult(is_duplicate=False, should_suggest_version=False)

        content_hash = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
        existing_versions: list = []
        try:
            async with async_session() as session:
                repo = VersionRepository(session)
                existing_versions = await repo.find_by_content_hash(content_hash, exclude_version_id=exclude_version_id)

            if existing_versions:
                existing = existing_versions[0]
                # Keep legacy event for backward compatibility
                logger.info("deduplication_hit_layer2", method="content_hash", version_id=str(existing.id))
                _log_check(
                    layer="L2_content_hash",
                    method="content_hash",
                    duration_ms=(time.perf_counter() - start) * 1000,
                    outcome="hit",
                    exclude_version_id=exclude_version_id,
                    input_text_len=len(extracted_text),
                    existing_version_id=existing.id,
                    extra={"content_hash": content_hash, "matches_found": len(existing_versions)},
                )
                return DeduplicationResult(
                    is_duplicate=True,
                    should_suggest_version=False,
                    existing_version_id=existing.id,
                    method="content_hash"
                )

            _log_check(
                layer="L2_content_hash",
                method="content_hash",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="miss",
                exclude_version_id=exclude_version_id,
                input_text_len=len(extracted_text),
                extra={"content_hash": content_hash},
            )
        except Exception as exc:
            _log_check(
                layer="L2_content_hash",
                method="content_hash",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="error",
                exclude_version_id=exclude_version_id,
                input_text_len=len(extracted_text) if extracted_text else 0,
                extra={"content_hash": content_hash, "error": str(exc)},
            )
            raise

        return DeduplicationResult(is_duplicate=False, should_suggest_version=False)

    async def check_semantic_duplicate(self, text: str, threshold: float = None) -> DeduplicationResult:
        """
        Layer 3: Near-duplicate detection via Semantic Fingerprint.

        NEW APPROACH: Multi-sample weighted embedding
        - Sample 1: first 3000 chars (weight 0.3) - introduction
        - Sample 2: middle 4000 chars (weight 0.5) - core content
        - Sample 3: last 2000 chars (weight 0.2) - conclusion

        Returns:
        - is_duplicate=True if similarity >= 0.98 (exact/near duplicate -> BLOCK)
        - should_suggest_version=True if 0.85 <= similarity < 0.98 (near duplicate -> SUGGEST VERSION)
        - Otherwise: unique document -> INGEST

        Returns the embedding used for the check as part of the result.
        """
        start = time.perf_counter()
        block_threshold = self.SEMANTIC_BLOCK_THRESHOLD
        version_threshold = threshold if threshold is not None else self.SEMANTIC_VERSION_THRESHOLD

        if not text:
            _log_check(
                layer="L3_semantic",
                method="semantic",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="skipped_empty",
                input_text_len=0,
                block_threshold=block_threshold,
                version_threshold=version_threshold,
            )
            return DeduplicationResult(is_duplicate=False, should_suggest_version=False)

        text_len = len(text)

        # Define sample regions for multi-sample approach
        samples = []

        # Sample 1: Head (first 3000 chars) - weight 0.3
        head_end = min(3000, text_len)
        samples.append((text[:head_end], 0.3))

        # Sample 2: Body (middle 4000 chars) - weight 0.5
        if text_len > 4000:
            body_start = (text_len - 4000) // 2
            body_end = body_start + 4000
            samples.append((text[body_start:body_end], 0.5))
        elif text_len > head_end:
            samples.append((text[head_end:], 0.5))

        # Sample 3: Tail (last 2000 chars) - weight 0.2
        if text_len > 2000:
            samples.append((text[-2000:], 0.2))
        elif text_len > head_end:
            remaining = text_len - head_end
            if remaining > 0:
                samples.append((text[head_end:], 0.2))

        # Generate embeddings for all samples
        texts_to_embed = [s[0] for s in samples]
        weights = [s[1] for s in samples]

        try:
            embeddings = await embedding_service.embed_batch(texts_to_embed)
        except Exception as exc:
            _log_check(
                layer="L3_semantic",
                method="semantic",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="error",
                input_text_len=text_len,
                block_threshold=block_threshold,
                version_threshold=version_threshold,
                extra={"stage": "embedding", "error": str(exc)},
            )
            raise

        if not embeddings or len(embeddings) != len(samples):
            _log_check(
                layer="L3_semantic",
                method="semantic",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="skipped_empty",
                input_text_len=text_len,
                block_threshold=block_threshold,
                version_threshold=version_threshold,
                extra={"stage": "embedding", "reason": "empty_result"},
            )
            return DeduplicationResult(is_duplicate=False, should_suggest_version=False)

        # Compute weighted average embedding
        import numpy as np
        weighted_embedding = np.zeros_like(embeddings[0], dtype=np.float32)
        for emb, weight in zip(embeddings, weights):
            if emb:
                weighted_embedding += np.array(emb) * weight
        # Normalize to unit vector
        norm = np.linalg.norm(weighted_embedding)
        if norm > 0:
            weighted_embedding = weighted_embedding / norm
        doc_embedding = weighted_embedding.tolist()

        embedding_dim = len(doc_embedding)

        near_duplicates: list = []
        try:
            async with async_session() as session:
                repo = VersionRepository(session)
                near_duplicates = await repo.find_near_duplicates(
                    doc_embedding, threshold=version_threshold
                )
        except Exception as exc:
            _log_check(
                layer="L3_semantic",
                method="semantic",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="error",
                input_text_len=text_len,
                fingerprint_len=sum(len(s[0]) for s in samples),
                embedding_dim=embedding_dim,
                block_threshold=block_threshold,
                version_threshold=version_threshold,
                extra={"stage": "vector_search", "error": str(exc)},
            )
            raise

        if near_duplicates:
            existing, similarity = near_duplicates[0]
            is_duplicate = similarity >= block_threshold
            should_suggest = (not is_duplicate) and similarity >= version_threshold

            logger.info(
                "deduplication_layer3_result",
                method="semantic",
                version_id=str(existing.id),
                similarity=similarity,
                is_duplicate=is_duplicate,
                should_suggest_version=should_suggest
            )
            _log_check(
                layer="L3_semantic",
                method="semantic",
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="hit",
                input_text_len=text_len,
                fingerprint_len=sum(len(s[0]) for s in samples),
                embedding_dim=embedding_dim,
                candidates_returned=len(near_duplicates),
                similarity=similarity,
                existing_version_id=existing.id,
                block_threshold=block_threshold,
                version_threshold=version_threshold,
                extra={
                    "decision": "block" if is_duplicate else ("suggest_version" if should_suggest else "below_version_threshold"),
                    "sample_count": len(samples),
                    "weights": weights
                },
            )
            return DeduplicationResult(
                is_duplicate=is_duplicate,
                should_suggest_version=should_suggest,
                existing_version_id=existing.id,
                method="semantic",
                similarity=similarity,
                vector=doc_embedding
            )

        _log_check(
            layer="L3_semantic",
            method="semantic",
            duration_ms=(time.perf_counter() - start) * 1000,
            outcome="miss",
            input_text_len=text_len,
            fingerprint_len=sum(len(s[0]) for s in samples),
            embedding_dim=embedding_dim,
            candidates_returned=0,
            block_threshold=block_threshold,
            version_threshold=version_threshold,
            extra={"sample_count": len(samples), "weights": weights},
        )
        return DeduplicationResult(is_duplicate=False, should_suggest_version=False, vector=doc_embedding)


# Global instance
deduplicator = Deduplicator()
