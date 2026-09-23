"""
test_deduplication.py
=====================
Unit + integration tests for the 3-layer deduplication system.

Test strategy
─────────────
Layer 1 – check_file_duplicate     : SHA-256 file checksum
Layer 2 – check_content_duplicate  : SHA-256 of extracted text
Layer 3 – check_semantic_duplicate : cosine-similar embedding fingerprint
Pipeline – IngestionPipeline.process: end-to-end orchestration

All external I/O is mocked so the suite runs offline with no DB / S3 / GPU.

Run
───
    pip install pytest pytest-asyncio
    pytest test_deduplication.py -v
"""

import hashlib
import sys
import types
import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs for every import the production modules need.
# We inject these into sys.modules BEFORE importing our code.
# ---------------------------------------------------------------------------

def _make_stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# structlog
structlog_stub = _make_stub_module("structlog")
structlog_stub.get_logger = lambda: MagicMock()
sys.modules.setdefault("structlog", structlog_stub)

# src.* package stubs (filled in per-test via patch where needed)
for pkg in [
    "src.db", "src.db.session",
    "src.db.repositories", "src.db.repositories.version_repo",
    "src.db.repositories.chunk_repo", "src.db.repositories.document_repo",
    "src.db.repositories.job_repo",
    "src.services.embedding_service",
    "src.services.minio_service", "src.services.processing_job_service",
    "src.services.extractors", "src.services.extractors.orchestrator",
    "src.services.standardizer", "src.services.chunker",
    "src.models", "src.models.extraction", "src.models.document",
]:
    sys.modules.setdefault(pkg, types.ModuleType(pkg))

# Provide concrete names that production code accesses at import time
sys.modules["src.db.session"].async_session = MagicMock()
sys.modules["src.db.repositories.version_repo"].VersionRepository = MagicMock()
sys.modules["src.db.repositories.chunk_repo"].ChunkRepository = MagicMock()
sys.modules["src.db.repositories.document_repo"].DocumentRepository = MagicMock()
sys.modules["src.db.repositories.job_repo"].JobRepository = MagicMock()

sys.modules["src.services.embedding_service"].embedding_service = MagicMock()
sys.modules["src.services.minio_service"].minio_service = MagicMock()
sys.modules["src.services.processing_job_service"].processing_job_service = MagicMock()
sys.modules["src.services.extractors.orchestrator"].orchestrator = MagicMock()
sys.modules["src.services.standardizer"].DocumentPolicyStandardizer = MagicMock()
sys.modules["src.services.chunker"].ParentChildChunker = MagicMock()

sys.modules["src.models.extraction"].Chunk = MagicMock()
sys.modules["src.models.document"].Document = MagicMock()

# Now we can safely import production code
from src.services.deduplicator import Deduplicator, DeduplicationResult  # noqa: E402
from src.services.pipeline import IngestionPipeline  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

EXISTING_VERSION_ID = uuid.uuid4()
NEW_VERSION_ID      = uuid.uuid4()
DOCUMENT_ID         = uuid.uuid4()
JOB_ID              = uuid.uuid4()


def _sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def _fake_embedding(seed: float = 0.1) -> list[float]:
    """Returns a simple 4-dim unit-like vector for testing."""
    return [seed, seed, seed, seed]


def _make_version_mock(version_id: uuid.UUID = EXISTING_VERSION_ID) -> MagicMock:
    v = MagicMock()
    v.id = version_id
    return v


def _make_async_session_cm(repo_mock: MagicMock):
    """Creates an async context manager that yields a session owning repo_mock."""
    session = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__  = AsyncMock(return_value=False)
    return cm, session


# ---------------------------------------------------------------------------
# ══════════════════════════════════════════════════════════════════
# LAYER 1 – file checksum
# ══════════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------

class TestLayer1FileChecksum:
    """SHA-256 byte-for-byte duplicate detection."""

    @pytest.mark.asyncio
    async def test_exact_same_file_is_flagged(self):
        """Uploading the identical file a second time must be caught."""
        file_bytes = b"Hello, this is a policy document."
        existing  = _make_version_mock()

        repo = MagicMock()
        repo.find_by_file_checksum = AsyncMock(return_value=existing)

        cm, session = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_file_duplicate(file_bytes)

        assert result.is_duplicate is True
        assert result.existing_version_id == existing.id
        assert result.method == "file_checksum"

    @pytest.mark.asyncio
    async def test_different_file_passes_layer1(self):
        """A new file must not be flagged as duplicate."""
        repo = MagicMock()
        repo.find_by_file_checksum = AsyncMock(return_value=None)

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_file_duplicate(b"Completely different bytes.")

        assert result.is_duplicate is False
        assert result.existing_version_id is None

    @pytest.mark.asyncio
    async def test_empty_file_runs_without_error(self):
        """Edge case: empty file bytes should not raise."""
        repo = MagicMock()
        repo.find_by_file_checksum = AsyncMock(return_value=None)

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_file_duplicate(b"")

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_same_content_different_encoding_hits_layer1(self):
        """
        PDF vs DOCX wrapping the same text still produces different raw bytes →
        Layer 1 must NOT flag this (Layer 2 will catch it instead).
        """
        pdf_bytes  = b"%PDF-1.4 fake-header Hello policy text"
        docx_bytes = b"PK\x03\x04 fake-zip Hello policy text"

        repo = MagicMock()
        repo.find_by_file_checksum = AsyncMock(return_value=None)  # no match

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result_pdf  = await Deduplicator().check_file_duplicate(pdf_bytes)
            result_docx = await Deduplicator().check_file_duplicate(docx_bytes)

        assert result_pdf.is_duplicate  is False
        assert result_docx.is_duplicate is False


# ---------------------------------------------------------------------------
# ══════════════════════════════════════════════════════════════════
# LAYER 2 – content hash
# ══════════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------

class TestLayer2ContentHash:
    """SHA-256 of extracted text – catches format-swap duplicates."""

    @pytest.mark.asyncio
    async def test_same_text_in_different_format_is_flagged(self):
        """Same extracted text from PDF and DOCX must be caught."""
        text     = "Annual safety policy v1.0 – all employees must comply."
        existing = _make_version_mock()

        repo = MagicMock()
        repo.find_by_content_hash = AsyncMock(return_value=[existing])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_content_duplicate(text)

        assert result.is_duplicate is True
        assert result.method == "content_hash"

    @pytest.mark.asyncio
    async def test_empty_text_skips_layer2(self):
        """Empty / None text should short-circuit without hitting the DB."""
        repo = MagicMock()
        repo.find_by_content_hash = AsyncMock()

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_content_duplicate("")

        assert result.is_duplicate is False
        repo.find_by_content_hash.assert_not_called()

    @pytest.mark.asyncio
    async def test_unique_text_passes_layer2(self):
        """Brand-new text must pass through."""
        repo = MagicMock()
        repo.find_by_content_hash = AsyncMock(return_value=[])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_content_duplicate("Totally new text.")

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_exclude_version_id_is_forwarded(self):
        """The exclude_version_id parameter must be passed to the repo unchanged."""
        exclude = uuid.uuid4()
        repo    = MagicMock()
        repo.find_by_content_hash = AsyncMock(return_value=[])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            await Deduplicator().check_content_duplicate("Some text", exclude_version_id=exclude)

        repo.find_by_content_hash.assert_called_once_with(
            _sha256("Some text"), exclude_version_id=exclude
        )

    @pytest.mark.asyncio
    async def test_minor_whitespace_change_creates_new_hash(self):
        """
        A document with trailing whitespace trimmed should NOT be flagged
        as a content duplicate (hash differs → falls through to Layer 3).
        """
        original_text = "Policy document text.\n\n"
        trimmed_text  = "Policy document text."

        repo = MagicMock()
        repo.find_by_content_hash = AsyncMock(return_value=[])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_content_duplicate(trimmed_text)

        assert result.is_duplicate is False


# ---------------------------------------------------------------------------
# ══════════════════════════════════════════════════════════════════
# LAYER 3 – semantic fingerprint
# ══════════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------

class TestLayer3Semantic:
    """Near-duplicate detection via embedding similarity."""

    @pytest.mark.asyncio
    async def test_semantically_similar_doc_is_flagged(self):
        """A document that is paraphrased but semantically identical must be caught."""
        text     = "Employees must follow the safety protocol at all times."
        existing = _make_version_mock()
        vec      = _fake_embedding(0.9)

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        repo.find_near_duplicates = AsyncMock(return_value=[(existing, 0.97)])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_semantic_duplicate(text, threshold=0.95)

        assert result.is_duplicate is True
        assert result.method == "semantic"
        assert result.similarity == 0.97
        assert result.vector == vec

    @pytest.mark.asyncio
    async def test_unique_document_not_flagged(self):
        """A genuinely new document must pass Layer 3 and return its embedding."""
        text = "Brand-new content never seen before."
        vec  = _fake_embedding(0.5)

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        repo.find_near_duplicates = AsyncMock(return_value=[])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_semantic_duplicate(text)

        assert result.is_duplicate is False
        assert result.vector == vec  # embedding is returned for downstream use

    @pytest.mark.asyncio
    async def test_empty_text_skips_layer3(self):
        """Empty text short-circuits before embedding call."""
        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock()

        with patch("src.services.deduplicator.embedding_service", emb_service):
            result = await Deduplicator().check_semantic_duplicate("")

        assert result.is_duplicate is False
        emb_service.embed_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_fingerprint_uses_only_first_4000_chars(self):
        """Only the first 4 000 chars should be sent to the embedding service."""
        long_text   = "A" * 10_000
        vec         = _fake_embedding()

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        repo.find_near_duplicates = AsyncMock(return_value=[])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            await Deduplicator().check_semantic_duplicate(long_text)

        call_args = emb_service.embed_batch.call_args[0][0]  # first positional arg (list)
        assert len(call_args[0]) == 4000, "Fingerprint must be exactly 4 000 chars"

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_not_duplicate(self):
        """If the embedding service returns empty, don't crash – treat as unique."""
        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[])  # empty list

        repo = MagicMock()
        repo.find_near_duplicates = AsyncMock()

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_semantic_duplicate("Some text")

        assert result.is_duplicate is False
        repo.find_near_duplicates.assert_not_called()

    @pytest.mark.asyncio
    async def test_below_threshold_not_flagged(self):
        """Similarity just below the threshold must NOT be flagged."""
        vec = _fake_embedding()

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        # Simulate repo filtering by threshold (returns nothing below 0.95)
        repo.find_near_duplicates = AsyncMock(return_value=[])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):

            result = await Deduplicator().check_semantic_duplicate("Slightly different doc.", threshold=0.95)

        assert result.is_duplicate is False


# ---------------------------------------------------------------------------
# ══════════════════════════════════════════════════════════════════
# PIPELINE – end-to-end orchestration
# ══════════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------

def _make_extracted(text: str = "Sample extracted text from document."):
    """Build a fake extraction result."""
    ex = MagicMock()
    ex.text       = text
    ex.page_count = 3
    return ex


def _make_pipeline_deps(
    *,
    file_bytes: bytes = b"fake-pdf-bytes",
    extracted_text: str = "Sample extracted text from document.",
    layer1_hit: bool = False,
    layer2_hit: bool = False,
    layer3_hit: bool = False,
    layer3_similarity: float = 0.99,
):
    """
    Returns a dict of patch targets → mock values covering all I/O in
    IngestionPipeline.process().
    """
    existing = _make_version_mock()
    vec      = _fake_embedding()

    # Deduplicator mocks
    dup_l1 = DeduplicationResult(
        is_duplicate=layer1_hit,
        existing_version_id=existing.id if layer1_hit else None,
        method="file_checksum" if layer1_hit else None,
    )
    dup_l2 = DeduplicationResult(
        is_duplicate=layer2_hit,
        existing_version_id=existing.id if layer2_hit else None,
        method="content_hash" if layer2_hit else None,
    )
    dup_l3 = DeduplicationResult(
        is_duplicate=layer3_hit,
        existing_version_id=existing.id if layer3_hit else None,
        method="semantic"     if layer3_hit else None,
        similarity=layer3_similarity if layer3_hit else None,
        vector=vec,
    )

    mock_dedup = MagicMock()
    mock_dedup.check_file_duplicate    = AsyncMock(return_value=dup_l1)
    mock_dedup.check_content_duplicate = AsyncMock(return_value=dup_l2)
    mock_dedup.check_semantic_duplicate= AsyncMock(return_value=dup_l3)

    # MinIO
    mock_minio = MagicMock()
    mock_minio.download_file = AsyncMock(return_value=file_bytes)

    # Extractor
    mock_orchestrator = MagicMock()
    mock_orchestrator.extract = AsyncMock(return_value=_make_extracted(extracted_text))

    # Job service
    mock_job_svc = MagicMock()
    mock_job_svc.update_progress = AsyncMock()
    mock_job_svc.complete_job    = AsyncMock()

    # DB session – generic pass-through
    ver_repo = MagicMock()
    ver_repo.update_version      = AsyncMock()
    doc_repo = MagicMock()
    doc_repo.update_extracted_text = AsyncMock()
    doc_repo.update_status       = AsyncMock()
    job_repo = MagicMock()
    job_repo.mark_failed         = AsyncMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__  = AsyncMock(return_value=False)

    def repo_factory(s):
        if s is session:
            return ver_repo
        return ver_repo

    return dict(
        mock_dedup=mock_dedup,
        mock_minio=mock_minio,
        mock_orchestrator=mock_orchestrator,
        mock_job_svc=mock_job_svc,
        session=session,
        ver_repo=ver_repo,
        doc_repo=doc_repo,
        job_repo=job_repo,
    )


def _patch_pipeline(deps: dict):
    """Context-manager helper – patches all pipeline external deps."""
    session = deps["session"]
    ver_repo = deps["ver_repo"]
    doc_repo = deps["doc_repo"]
    job_repo = deps["job_repo"]

    # VersionRepository / DocumentRepository / JobRepository are constructed
    # inside async with blocks; we need side_effect to return the right mock.
    def ver_repo_factory(_):  return ver_repo
    def doc_repo_factory(_):  return doc_repo
    def job_repo_factory(_):  return job_repo

    return [
        patch("src.services.pipeline.deduplicator",            deps["mock_dedup"]),
        patch("src.services.pipeline.minio_service",           deps["mock_minio"]),
        patch("src.services.pipeline.orchestrator",            deps["mock_orchestrator"]),
        patch("src.services.pipeline.processing_job_service",  deps["mock_job_svc"]),
        patch("src.services.pipeline.async_session",           return_value=session),
        patch("src.services.pipeline.VersionRepository",       side_effect=ver_repo_factory),
        patch("src.services.pipeline.DocumentRepository",      side_effect=doc_repo_factory),
        patch("src.services.pipeline.JobRepository",           side_effect=job_repo_factory),
    ]


class TestPipelineEndToEnd:
    """Full pipeline orchestration scenarios."""

    @pytest.mark.asyncio
    async def test_clean_new_document_completes_successfully(self):
        """A document that passes all 3 layers must reach status=completed."""
        deps = _make_pipeline_deps()

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            result = await IngestionPipeline().process(
                document_id=DOCUMENT_ID,
                version_id=NEW_VERSION_ID,
                job_id=JOB_ID,
                bucket_name="docs",
                file_key="file.pdf",
                metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        assert result["status"] == "completed"
        assert result["document_id"] == str(DOCUMENT_ID)

    @pytest.mark.asyncio
    async def test_layer1_hit_returns_skipped(self):
        """Exact same file must short-circuit at Layer 1 → status=skipped."""
        deps = _make_pipeline_deps(layer1_hit=True)

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            result = await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="file.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        assert result["status"]  == "skipped"
        assert result["reason"]  == "duplicate"
        assert result["method"]  == "file_checksum"
        # Layer 2 & 3 must NOT have been called
        deps["mock_dedup"].check_content_duplicate.assert_not_called()
        deps["mock_dedup"].check_semantic_duplicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_layer2_hit_returns_skipped_and_skips_layer3(self):
        """Same text in different format must be caught by Layer 2 → skipped."""
        deps = _make_pipeline_deps(layer2_hit=True)

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            result = await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="file.docx", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        assert result["status"] == "skipped"
        assert result["method"] == "content_hash"
        deps["mock_dedup"].check_semantic_duplicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_layer3_hit_blocks_ingestion(self):
        """
        Semantic duplicate must block ingestion and return a skipped status.
        """
        deps = _make_pipeline_deps(layer3_hit=True, layer3_similarity=0.99)

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            result = await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="new_version.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        assert result["status"] == "skipped"
        assert result["reason"] == "duplicate"
        assert result["method"] == "semantic"
        deps["doc_repo"].update_status.assert_called_with(DOCUMENT_ID, "DUPLICATE")

        # complete_job must report the similarity in its payload
        call_kwargs = deps["mock_job_svc"].complete_job.call_args
        result_data = call_kwargs[0][2] if call_kwargs[0] else call_kwargs[1].get("result", {})
        assert result_data.get("similarity") == 0.99

    @pytest.mark.asyncio
    async def test_extraction_failure_marks_document_failed(self):
        """An exception during extraction must result in status=FAILED."""
        deps = _make_pipeline_deps()
        deps["mock_orchestrator"].extract = AsyncMock(side_effect=RuntimeError("OCR engine crash"))

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            result = await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="corrupt.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        assert result["status"] == "FAILED"
        assert "OCR engine crash" in result["error"]

    @pytest.mark.asyncio
    async def test_minio_failure_marks_document_failed(self):
        """S3/MinIO download failure must be caught and recorded."""
        deps = _make_pipeline_deps()
        deps["mock_minio"].download_file = AsyncMock(side_effect=ConnectionError("S3 unreachable"))

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            result = await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="file.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        assert result["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_checksums_are_computed_and_saved(self):
        """
        After passing all 3 layers, the pipeline must persist both
        file_checksum and content_hash to the version record.
        """
        file_bytes = b"Real document bytes for checksum test."
        text       = "Real document text for content hash test."
        deps       = _make_pipeline_deps(file_bytes=file_bytes, extracted_text=text)

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="file.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        expected_file_checksum    = _sha256(file_bytes)
        expected_content_checksum = _sha256(text)

        deps["ver_repo"].update_version.assert_called_once_with(
            NEW_VERSION_ID,
            file_checksum=expected_file_checksum,
            content_hash=expected_content_checksum,
        )

    @pytest.mark.asyncio
    async def test_progress_updates_are_emitted(self):
        """Pipeline must emit at least 3 progress checkpoints."""
        deps = _make_pipeline_deps()

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="file.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        assert deps["mock_job_svc"].update_progress.await_count >= 3

    @pytest.mark.asyncio
    async def test_duplicate_document_status_set_to_duplicate(self):
        """When any dedup layer fires, document status must be set to DUPLICATE."""
        deps = _make_pipeline_deps(layer1_hit=True)

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="file.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        deps["doc_repo"].update_status.assert_called_with(DOCUMENT_ID, "DUPLICATE")


# ---------------------------------------------------------------------------
# ══════════════════════════════════════════════════════════════════
# NEAR-DUPLICATE TESTS – 3-way threshold (0.85, 0.98)
# ══════════════════════════════════════════════════════════════════
# ---------------------------------------------------------------------------

class TestNearDuplicateThreshold:
    """Tests for the 3-way semantic duplicate threshold decision."""

    @pytest.mark.asyncio
    async def test_semantic_duplicate_at_098_is_block(self):
        """Similarity >= 0.98 → is_duplicate=True, should_suggest_version=False."""
        text = "Employees must follow all safety protocols."
        vec = _fake_embedding()
        existing = _make_version_mock()

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        repo.find_near_duplicates = AsyncMock(return_value=[(existing, 0.99)])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):
            deduplicator = Deduplicator()
            result = await deduplicator.check_semantic_duplicate(text)

        assert result.is_duplicate is True
        assert result.should_suggest_version is False
        assert result.similarity == 0.99
        assert result.method == "semantic"

    @pytest.mark.asyncio
    async def test_semantic_duplicate_at_092_suggests_version(self):
        """0.85 <= similarity < 0.98 → is_duplicate=False, should_suggest_version=True."""
        text = "This is a slightly paraphrased version of a policy document."
        vec = _fake_embedding()
        existing = _make_version_mock()

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        repo.find_near_duplicates = AsyncMock(return_value=[(existing, 0.92)])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):
            deduplicator = Deduplicator()
            result = await deduplicator.check_semantic_duplicate(text)

        assert result.is_duplicate is False
        assert result.should_suggest_version is True
        assert result.similarity == 0.92
        assert result.existing_version_id == existing.id

    @pytest.mark.asyncio
    async def test_semantic_duplicate_at_085_suggests_version(self):
        """Similarity == 0.85 (lower boundary) → should_suggest_version=True."""
        text = "Lower boundary test document."
        vec = _fake_embedding()
        existing = _make_version_mock()

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        repo.find_near_duplicates = AsyncMock(return_value=[(existing, 0.85)])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):
            deduplicator = Deduplicator()
            result = await deduplicator.check_semantic_duplicate(text)

        assert result.is_duplicate is False
        assert result.should_suggest_version is True
        assert result.similarity == 0.85

    @pytest.mark.asyncio
    async def test_semantic_duplicate_below_085_is_unique(self):
        """Similarity < 0.85 → is_duplicate=False, should_suggest_version=False."""
        text = "Completely different document content."
        vec = _fake_embedding()
        existing = _make_version_mock()

        emb_service = MagicMock()
        emb_service.embed_batch = AsyncMock(return_value=[vec])

        repo = MagicMock()
        # No near-duplicates found (below version threshold)
        repo.find_near_duplicates = AsyncMock(return_value=[])

        cm, _ = _make_async_session_cm(repo)

        with patch("src.services.deduplicator.embedding_service", emb_service), \
             patch("src.services.deduplicator.async_session", return_value=cm), \
             patch("src.services.deduplicator.VersionRepository", return_value=repo):
            deduplicator = Deduplicator()
            result = await deduplicator.check_semantic_duplicate(text)

        assert result.is_duplicate is False
        assert result.should_suggest_version is False
        assert result.existing_version_id is None

    @pytest.mark.asyncio
    async def test_deduplication_result_has_should_suggest_version_field(self):
        """DeduplicationResult NamedTuple includes should_suggest_version field."""
        from src.services.deduplicator import DeduplicationResult

        result = DeduplicationResult(
            is_duplicate=False,
            should_suggest_version=True,
            existing_version_id=EXISTING_VERSION_ID,
            method="semantic",
            similarity=0.92,
            vector=[0.1, 0.2, 0.3, 0.4]
        )

        assert result.is_duplicate is False
        assert result.should_suggest_version is True
        assert result.existing_version_id == EXISTING_VERSION_ID
        assert result.similarity == 0.92


class TestPipelineNearDuplicate:
    """Tests for pipeline handling of near-duplicates."""

    @pytest.mark.asyncio
    async def test_near_duplicate_continues_ingestion(self):
        """Near-duplicate (should_suggest_version=True) should continue ingestion."""
        deps = _make_pipeline_deps()
        # Override layer 3 to return near-duplicate
        existing = _make_version_mock()
        vec = _fake_embedding()

        dup_l3 = DeduplicationResult(
            is_duplicate=False,
            should_suggest_version=True,
            existing_version_id=existing.id,
            method="semantic",
            similarity=0.92,
            vector=vec,
        )
        deps["mock_dedup"].check_semantic_duplicate = AsyncMock(return_value=dup_l3)

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            result = await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="new_doc.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        # Pipeline should complete successfully (not skip)
        assert result["status"] == "completed"

        # Near-duplicate info should be in output metrics
        deps["mock_job_svc"].complete_job.assert_called_once()
        call_args = deps["mock_job_svc"].complete_job.call_args
        metrics = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("metrics", {})
        assert "near_duplicate" in metrics
        assert metrics["near_duplicate"] is not None
        assert metrics["near_duplicate"]["similarity"] == 0.92

    @pytest.mark.asyncio
    async def test_near_duplicate_info_includes_existing_version_id(self):
        """Near-duplicate metrics should include the existing version ID."""
        deps = _make_pipeline_deps()
        existing = _make_version_mock()
        vec = _fake_embedding()

        dup_l3 = DeduplicationResult(
            is_duplicate=False,
            should_suggest_version=True,
            existing_version_id=existing.id,
            method="semantic",
            similarity=0.92,
            vector=vec,
        )
        deps["mock_dedup"].check_semantic_duplicate = AsyncMock(return_value=dup_l3)

        patches = _patch_pipeline(deps)
        for p in patches:
            p.start()
        try:
            await IngestionPipeline().process(
                document_id=DOCUMENT_ID, version_id=NEW_VERSION_ID, job_id=JOB_ID,
                bucket_name="docs", file_key="doc.pdf", metadata={},
            )
        finally:
            for p in patches:
                p.stop()

        deps["mock_job_svc"].complete_job.assert_called_once()
        call_args = deps["mock_job_svc"].complete_job.call_args
        metrics = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("metrics", {})
        near_dup = metrics["near_duplicate"]
        assert near_dup["existing_version_id"] == str(existing.id)
        assert near_dup["similarity"] == 0.92
        assert near_dup["method"] == "semantic"