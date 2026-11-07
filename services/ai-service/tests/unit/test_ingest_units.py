"""V2-09 step 1 units: BM25 tokenizer, models.yaml, embedding providers, ingest pipeline,
language detection, failure messages and outbox rules. No database, no model download."""
from __future__ import annotations

import json
from collections import Counter
from uuid import uuid4

import httpx
import numpy as np
import pytest

from fakes import Words
from sopilot_ai.config import SERVICE_ROOT
from sopilot_ai.db.engine import parse_vector, sqlalchemy_url, vector_literal
from sopilot_ai.db.repositories.outbox import OutboxEvent
from sopilot_ai.docproc import ChunkConfig, DocFamily, ExtractionError, FailureCode
from sopilot_ai.ingest import failures
from sopilot_ai.ingest.language import detect_language
from sopilot_ai.ingest.pipeline import chunk_type, process_document
from sopilot_ai.ingest.schemas import IngestionRequest
from sopilot_ai.outbox.dispatcher import backoff_seconds, body_for, request_for
from sopilot_ai.providers.embedding import (
    UNPINNED,
    EmbeddingError,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
    resolve_revision,
)
from sopilot_ai.providers.registry import ModelsConfig
from sopilot_ai.retrieval.lexical import (
    FOLD_PREFIX,
    base_terms,
    lexical_len,
    term_frequencies,
    tokenize,
)

SOP_MD = """---
title: Quy trình mua hàng
---
# Quy trình mua hàng

## 1. Mục đích

Quy định cách lập và duyệt đề nghị mua hàng trong công ty để kiểm soát chi phí.

## 2. Phạm vi

Áp dụng cho mọi phòng ban có nhu cầu mua hàng hóa và dịch vụ.

## 3. Nội dung

| Bước | Trách nhiệm | Mô tả |
|---|---|---|
| 1 | Nhân viên | Lập phiếu đề nghị mua hàng |
| 2 | Trưởng phòng | Duyệt đề nghị và chuyển phòng mua hàng |
"""


# -- BM25 tokenizer (TECH-V2-ai-service §6.3) -----------------------------------------------------

def test_document_terms_add_folded_terms_with_same_tf() -> None:
    tf = term_frequencies("Quy trình mua hàng, mua hàng")
    assert tf["hàng"] == 2 and tf[FOLD_PREFIX + "hang"] == 2
    assert tf["mua_hàng"] == 2 and tf[FOLD_PREFIX + "mua_hang"] == 2
    assert FOLD_PREFIX + "mua" not in tf  # unchanged when folded: no extra term
    text = "Quy trình mua hàng, mua hàng"
    assert lexical_len(text) == len(base_terms(text))


def test_query_without_diacritics_matches_accented_document() -> None:
    doc = set(tokenize("Quy trình mua hàng", "document"))
    query = tokenize("quy trinh mua hang", "query")
    assert {FOLD_PREFIX + "trinh", FOLD_PREFIX + "mua_hang"} <= doc & set(query)


def test_query_with_diacritics_and_english_use_base_terms_only() -> None:
    assert tokenize("quy trình mua hàng", "query") == base_terms("quy trình mua hàng")
    english = tokenize("purchase approval", "query")
    assert set(base_terms("purchase approval")) <= set(english)
    assert set(base_terms("purchase approval")) <= set(tokenize("Purchase approval", "document"))


def test_tokenizer_matches_harness_reference_cases() -> None:
    # Expected values follow eval/sopilot_eval/retrievers.py::tokenize (V2-07).
    assert tokenize("Đơn hàng", "document") == ["đơn", "hàng", "đơn_hàng", "~don", "~hang",
                                                "~don_hang"]
    assert tokenize("don hang", "query") == ["don", "hang", "don_hang", "~don", "~hang",
                                             "~don_hang"]
    with pytest.raises(ValueError):
        tokenize("x", "other")  # type: ignore[arg-type]


# -- models.yaml --------------------------------------------------------------------------------

def test_models_yaml_expands_env_and_types(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_REVISION", "abc123")
    monkeypatch.setenv("RERANK_ENABLED", "true")
    config = ModelsConfig.load(SERVICE_ROOT / "config" / "models.yaml")
    spec = config.embedding()
    assert (spec.provider, spec.model, spec.revision, spec.dim) == ("local", "BAAI/bge-m3",
                                                                    "abc123", 1024)
    assert config.raw["rerank"]["enabled"] is True
    assert config.chunking() == ChunkConfig(target_tokens=384, max_tokens=512, min_tokens=64)
    monkeypatch.delenv("EMBEDDING_REVISION")
    assert ModelsConfig.load(SERVICE_ROOT / "config" / "models.yaml").embedding().revision == ""


def test_unpinned_revision_rules() -> None:
    spec = ModelsConfig({"embedding": {"active": "m", "models": {"m": {
        "provider": "local", "model": "x/y", "revision": "", "dim": 1024}}}}).embedding()
    assert resolve_revision(spec, "local") == UNPINNED
    with pytest.raises(RuntimeError):
        resolve_revision(spec, "eval")


def test_unknown_provider_is_rejected() -> None:
    config = ModelsConfig({"embedding": {"active": "m", "models": {"m": {
        "provider": "magic", "model": "x/y", "revision": "r", "dim": 1024}}}})
    with pytest.raises(ValueError):
        build_embedding_provider(config, "local")


def _openai_provider(handler) -> OpenAICompatibleEmbeddingProvider:
    config = ModelsConfig({
        "embedding": {"active": "m", "models": {"m": {
            "provider": "openai_compatible", "model": "x/y", "revision": "r", "dim": 3}}},
        "providers": {"openai_compatible": {"base_url": "http://tei/v1", "api_key_env": None}},
    })
    provider = build_embedding_provider(config, "local")
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    provider._client = httpx.Client(base_url="http://tei/v1",
                                    transport=httpx.MockTransport(handler))
    return provider


def test_openai_compatible_provider_orders_and_normalises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/embeddings" and body["model"] == "x/y"
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [0, 3, 4]}, {"index": 0, "embedding": [2, 0, 0]}]})

    out = _openai_provider(handler).embed(["a", "b"], is_query=False)
    np.testing.assert_allclose(out, [[1, 0, 0], [0, 0.6, 0.8]], atol=1e-6)


@pytest.mark.parametrize("response", [
    httpx.Response(503),
    httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]}),  # wrong dim
    httpx.Response(200, json={"oops": True}),
])
def test_openai_compatible_provider_errors_are_embedding_errors(response: httpx.Response) -> None:
    provider = _openai_provider(lambda _req: response)
    with pytest.raises(EmbeddingError):
        provider.embed(["a"], is_query=False)


# -- ingest pipeline (docproc wiring) --------------------------------------------------------------

def test_process_markdown_sop() -> None:
    processed = process_document(SOP_MD.encode("utf-8"), "MD", title="Quy trình mua hàng",
                                 tokenizer=Words(), chunk_config=ChunkConfig())
    assert processed.family is DocFamily.ISO_PROCEDURE
    assert processed.language == "vi"
    assert processed.page_index is None and processed.page_count is None
    assert processed.extractor.startswith("markdown-it-py ")
    assert processed.chunks
    for c in processed.chunks:
        assert 0 <= c.char_start < c.char_end <= len(processed.markdown)
        assert c.index_text.startswith("Quy trình mua hàng")
    kinds = Counter(chunk_type(c.kind, processed.family) for c in processed.chunks)
    assert kinds["PROCEDURE_STEP"] == 2 and set(kinds) <= {"SECTION", "PROCEDURE_STEP", "TABLE"}
    step = next(c for c in processed.chunks if c.kind == "PROCEDURE_STEP"
                and "Trưởng phòng" in c.content)
    assert "Duyệt" in step.content
    assert set(processed.meta) >= {"docCode", "revisionLabel", "effectiveDate", "approvedBy"}
    assert processed.structure["file_type"] == "MD"
    assert {"extract_ms", "clean_ms", "chunk_ms"} <= set(processed.timings)


@pytest.mark.parametrize("file_type", ["DOCX", "TXT"])
def test_unsupported_types_fail_before_parsing(file_type: str) -> None:
    with pytest.raises(ExtractionError) as err:
        process_document(b"hello", file_type, title="t", tokenizer=Words(),
                         chunk_config=ChunkConfig())
    assert err.value.code is FailureCode.UNSUPPORTED_TYPE


def test_markdown_that_is_not_utf8_is_invalid_encoding() -> None:
    with pytest.raises(ExtractionError) as err:
        process_document("Quy trình".encode("utf-16"), "MD", title="t", tokenizer=Words(),
                         chunk_config=ChunkConfig())
    assert err.value.code is FailureCode.INVALID_ENCODING


def test_chunk_type_mapping() -> None:
    assert chunk_type("TEXT", DocFamily.PROSE) == "PROSE"
    assert chunk_type("TEXT", DocFamily.MARKDOWN) == "SECTION"
    assert chunk_type("TABLE", DocFamily.PROSE) == "TABLE"
    assert chunk_type("PROCEDURE_STEP", DocFamily.ISO_PROCEDURE) == "PROCEDURE_STEP"


@pytest.mark.parametrize(("text", "expected"), [
    ("Quy trình này quy định cách lập và duyệt đề nghị mua hàng của công ty.", "vi"),
    ("This procedure describes how purchase requests are raised and approved by the team.", "en"),
    ("1 2 3", None),
])
def test_detect_language(text: str, expected: str | None) -> None:
    assert detect_language(text) == expected


def test_failure_messages_are_fixed_text() -> None:
    assert failures.failure_message("NO_TEXT_LAYER").startswith("PDF không có lớp chữ")
    assert failures.failure_message(failures.OBJECT_NOT_FOUND, "en").startswith("The uploaded")
    assert failures.failure_message("SOMETHING_NEW") == failures.failure_message("EXTRACTION_ERROR")


def test_ingestion_request_contract() -> None:
    body = {
        "workspaceId": str(uuid4()), "documentId": str(uuid4()), "versionId": str(uuid4()),
        "versionNo": 2, "objectKey": "workspaces/a/b", "sha256": "ab" * 32, "attempt": 0,
        "fileType": "PDF", "mimeType": "application/pdf", "originalName": "QT-MH-01.pdf",
        "title": "Quy trình mua hàng",
        "access": {"visibility": "DEPARTMENTS", "departmentIds": [str(uuid4())],
                   "accessRevision": 3},
        "suggest": {"enabled": True, "categories": [{"id": str(uuid4()), "name": "Mua sắm"}],
                    "tags": ["ISO"]},
    }
    req = IngestionRequest.model_validate(body)
    assert req.model_dump(mode="json", by_alias=True)["access"]["accessRevision"] == 3
    body["access"] = {"visibility": "DEPARTMENTS", "departmentIds": [], "accessRevision": 1}
    with pytest.raises(ValueError):
        IngestionRequest.model_validate(body)


# -- small helpers --------------------------------------------------------------------------------

def test_vector_literal_round_trip_and_url() -> None:
    v = np.array([0.5, -0.25, 1e-9], dtype=np.float32)
    np.testing.assert_allclose(parse_vector(vector_literal(v)), v, rtol=1e-6)
    assert sqlalchemy_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"


def test_outbox_request_mapping_and_backoff() -> None:
    doc, ver = uuid4(), uuid4()
    event = OutboxEvent(id=uuid4(), workspace_id=uuid4(), aggregate_id=doc,
                        event_type="VERSION_STATUS",
                        payload={"workspaceId": "w", "versionId": str(ver), "status": "READY"},
                        attempts=0)
    assert request_for(event) == ("PATCH", f"/internal/documents/{doc}/versions/{ver}/status")
    assert "versionId" not in body_for(event)
    assert backoff_seconds(30) <= 600 * 1.2
    assert 0.8 * 2 <= backoff_seconds(1) <= 1.2 * 2
