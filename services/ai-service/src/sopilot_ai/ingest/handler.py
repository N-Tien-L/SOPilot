"""Run one claimed ingestion job end to end (TECH-V2-ai-service §2.1, §5.1, §5.5, §5.6).

Failure handling (§5.1):
- content errors (``docproc.ExtractionError``, or anything unexpected in steps 2–5 as
  ``EXTRACTION_ERROR``) fail the job at once with one ``FAILED`` callback;
- transient errors (``OBJECT_NOT_FOUND``, ``EMBEDDING_ERROR``, storage or database outages) put
  the job back in the queue with ``run_after`` backoff and send nothing; after
  ``SOPILOT_INGEST_MAX_ATTEMPTS`` the job fails with the last code, or ``RETRY_EXHAUSTED`` when
  no code was ever recorded (for example the worker died and the lease expired).

A job re-queued by ``admin reindex`` (payload ``reindex: true``) sends no status callback at all:
the version stays ``READY`` in core-api and keeps its old chunks until the new ones activate.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import numpy as np
import structlog
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.db.engine import system_tx, tenant_tx
from sopilot_ai.db.repositories import embedding_cache, jobs, outbox, suggestions
from sopilot_ai.db.repositories.ingest import (
    ChunkRow,
    EmbeddingInfo,
    ExtractedRow,
    activate_version,
)
from sopilot_ai.db.repositories.jobs import ClaimedJob
from sopilot_ai.docproc import ChunkConfig, CleanConfig, ExtractionError, Tokenizer
from sopilot_ai.ingest import failures
from sopilot_ai.ingest.pipeline import ProcessedVersion, chunk_type, process_document
from sopilot_ai.ingest.schemas import IngestionRequest
from sopilot_ai.ingest.storage import ObjectNotFound, ObjectStore, StorageUnavailable
from sopilot_ai.providers.embedding import EmbeddingError, EmbeddingProvider
from sopilot_ai.retrieval.lexical import lexical_len, term_frequencies

log = structlog.get_logger(__name__)


@dataclass
class IngestDeps:
    engine: AsyncEngine
    store: ObjectStore
    embedder: EmbeddingProvider
    tokenizer: Tokenizer
    chunk_config: ChunkConfig
    clean_config: CleanConfig | None = None
    max_attempts: int = 3
    backoff_base_seconds: float = 30.0


class _Transient(Exception):
    def __init__(self, code: str | None) -> None:
        super().__init__(code or "transient")
        self.code = code


class _Cancelled(Exception):
    """The document was deleted, or a newer version is already active."""


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


async def handle_job(job: ClaimedJob, deps: IngestDeps) -> str:
    """Process ``job``; returns the resulting job status (for logs and tests)."""
    bound = log.bind(job_id=str(job.id), version_id=str(job.version_id), attempt=job.attempts)
    request = IngestionRequest.model_validate(job.payload)

    if job.attempts > deps.max_attempts:  # lease expired on the last allowed attempt
        await _fail(deps, job, request, job.failure_code or failures.RETRY_EXHAUSTED, None)
        bound.error("ingest_retry_exhausted", failure_code=job.failure_code)
        return "FAILED"

    if job.attempts == 1 and not _is_reindex(job):  # first run since core-api (re)queued it
        async with tenant_tx(deps.engine, job.workspace_id) as conn:
            await outbox.add(conn, workspace_id=job.workspace_id, aggregate_id=job.document_id,
                             event_type="VERSION_STATUS",
                             payload=_status_payload(job, request, "PROCESSING"))

    timings: dict[str, Any] = {}
    try:
        processed = await _download_and_process(job, request, deps, timings)
        vectors = await _embed(processed, deps, timings)
        t = time.perf_counter()
        status = await _activate(job, request, processed, vectors, deps, timings, t)
    except ExtractionError as exc:
        await _fail(deps, job, request, exc.code.value, timings)
        bound.info("ingest_failed", failure_code=exc.code.value)
        return "FAILED"
    except _Transient as exc:
        return await _transient(deps, job, request, exc.code, timings, bound)
    except _Cancelled:
        async with tenant_tx(deps.engine, job.workspace_id) as conn:
            await jobs.finish(conn, job.id, "CANCELLED", None, timings)
        bound.info("ingest_cancelled")
        return "CANCELLED"
    except (DBAPIError, OSError) as exc:
        bound.warning("ingest_infrastructure_error", error=type(exc).__name__)
        return await _transient(deps, job, request, None, timings, bound)
    bound.info("ingest_done", chunks=len(processed.chunks), **timings)
    return status


async def _download_and_process(job: ClaimedJob, request: IngestionRequest, deps: IngestDeps,
                                timings: dict[str, Any]) -> ProcessedVersion:
    t = time.perf_counter()
    try:
        data = await asyncio.to_thread(deps.store.get, request.object_key)
    except ObjectNotFound as exc:
        raise _Transient(failures.OBJECT_NOT_FOUND) from exc
    except StorageUnavailable as exc:
        raise _Transient(None) from exc
    timings["download_ms"] = _ms(t)
    try:
        processed = await asyncio.to_thread(
            process_document, data, request.file_type, title=request.title,
            tokenizer=deps.tokenizer, chunk_config=deps.chunk_config,
            clean_config=deps.clean_config)
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001 - steps 2–5 unknown error is EXTRACTION_ERROR (§5.1)
        log.exception("ingest_extraction_crashed", job_id=str(job.id))
        raise ExtractionError(failures.FailureCode.EXTRACTION_ERROR) from exc
    timings.update(processed.timings)
    return processed


async def _embed(processed: ProcessedVersion, deps: IngestDeps,
                 timings: dict[str, Any]) -> list[np.ndarray]:
    """§5.5: look up ``(model, revision, sha256(index_text))``, embed only what is missing."""
    t = time.perf_counter()
    model, revision = deps.embedder.model, deps.embedder.revision
    hashes = [hashlib.sha256(c.index_text.encode("utf-8")).digest() for c in processed.chunks]
    async with system_tx(deps.engine) as conn:
        cached = await embedding_cache.get_many(conn, model, revision, list(set(hashes)))
    missing = sorted({h: i for i, h in enumerate(hashes) if h not in cached}.items(),
                     key=lambda kv: kv[1])
    batch = getattr(getattr(deps.embedder, "spec", None), "batch_size", 16)
    fresh: list[tuple[bytes, np.ndarray]] = []
    for start in range(0, len(missing), batch):
        part = missing[start:start + batch]
        texts = [processed.chunks[i].index_text for _, i in part]
        try:
            out = await asyncio.to_thread(deps.embedder.embed, texts, is_query=False)
        except EmbeddingError as exc:
            raise _Transient(failures.EMBEDDING_ERROR) from exc
        if out.shape != (len(texts), deps.embedder.dim):
            raise _Transient(failures.EMBEDDING_ERROR)
        fresh += [(h, out[k]) for k, (h, _) in enumerate(part)]
    if fresh:
        async with system_tx(deps.engine) as conn:
            await embedding_cache.put_many(conn, model, revision, fresh)
    vectors = {**cached, **dict(fresh)}
    timings["embed_ms"] = _ms(t)
    timings["embed_cached"] = len(hashes) - len(missing)
    return [vectors[h] for h in hashes]


async def _activate(job: ClaimedJob, request: IngestionRequest, processed: ProcessedVersion,
                    vectors: list[np.ndarray], deps: IngestDeps, timings: dict[str, Any],
                    started: float) -> str:
    rows = [
        ChunkRow(
            id=uuid4(), ordinal=i, chunk_type=chunk_type(c.kind, processed.family),
            section_path=list(c.section_path), page_start=c.page_start, page_end=c.page_end,
            char_start=c.char_start, char_end=c.char_end, content=c.content,
            index_text=c.index_text, lang=processed.language, token_count=c.token_count,
            content_sha256=hashlib.sha256(c.index_text.encode("utf-8")).digest(),
            embedding=vectors[i], lexical_len=lexical_len(c.index_text),
            terms=dict(term_frequencies(c.index_text)),
        )
        for i, c in enumerate(processed.chunks)
    ]
    extracted = ExtractedRow(
        structure=processed.structure, markdown=processed.markdown,
        page_index=processed.page_index, warnings=processed.warnings,
        normalizer_version=processed.normalizer_version, page_count=processed.page_count,
        language=processed.language, doc_family=processed.family.value,
        boilerplate=processed.boilerplate, extracted_meta=processed.meta,
        extractor=processed.extractor,
    )
    info = EmbeddingInfo(provider=deps.embedder.name, model=deps.embedder.model,
                         revision=deps.embedder.revision, dim=deps.embedder.dim)
    async with tenant_tx(deps.engine, job.workspace_id) as conn:
        if await jobs.newer_version_done(conn, job.document_id, request.version_no):
            raise _Cancelled()
        ok = await activate_version(conn, workspace_id=job.workspace_id,
                                    document_id=job.document_id, version_id=job.version_id,
                                    title=request.title, extracted=extracted, chunks=rows,
                                    embedding=info)
        if not ok:
            raise _Cancelled()  # leaving the block rolls the inserts back
        timings["write_ms"] = _ms(started)
        await jobs.finish(conn, job.id, "DONE", None, timings)
        if _is_reindex(job):
            return "DONE"
        if request.suggest is not None and request.suggest.enabled:
            # V2-25: queued in the same transaction: a suggestion exists only for a READY version.
            await suggestions.enqueue(
                conn, workspace_id=job.workspace_id, document_id=job.document_id,
                version_id=job.version_id,
                input={"sha256": request.sha256, "title": request.title,
                       "categories": [{"id": str(c.id), "name": c.name}
                                      for c in request.suggest.categories],
                       "tags": list(request.suggest.tags)})
        payload = _status_payload(job, request, "READY")
        payload.update({
            "pageCount": processed.page_count,
            "detectedLanguage": processed.language,
            "chunkCount": len(rows),
            "embedding": {"provider": info.provider, "model": info.model,
                          "revision": info.revision, "dim": info.dim},
            "extracted": processed.meta,
            "warningCodes": list(dict.fromkeys(w["code"] for w in processed.warnings)),
        })
        await outbox.add(conn, workspace_id=job.workspace_id, aggregate_id=job.document_id,
                         event_type="VERSION_STATUS", payload=payload)
    return "DONE"


async def _transient(deps: IngestDeps, job: ClaimedJob, request: IngestionRequest,
                     code: str | None, timings: dict[str, Any], bound: Any) -> str:
    last_code = code or job.failure_code
    if job.attempts >= deps.max_attempts:
        await _fail(deps, job, request, last_code or failures.RETRY_EXHAUSTED, timings)
        bound.error("ingest_failed_after_retries", failure_code=last_code)
        return "FAILED"
    delay = deps.backoff_base_seconds * 2 ** (job.attempts - 1)
    async with tenant_tx(deps.engine, job.workspace_id) as conn:
        await jobs.requeue(conn, job.id, last_code, delay, timings)
    bound.warning("ingest_retry_scheduled", failure_code=last_code, delay_s=delay)
    return "QUEUED"


async def _fail(deps: IngestDeps, job: ClaimedJob, request: IngestionRequest, code: str,
                timings: dict[str, Any] | None) -> None:
    async with tenant_tx(deps.engine, job.workspace_id) as conn:
        await jobs.finish(conn, job.id, "FAILED", code, timings)
        if _is_reindex(job):
            log.error("reindex_failed", version_id=str(job.version_id), failure_code=code)
            return
        payload = _status_payload(job, request, "FAILED")
        payload.update({"failureCode": code, "failureMessage": failures.failure_message(code)})
        await outbox.add(conn, workspace_id=job.workspace_id, aggregate_id=job.document_id,
                         event_type="VERSION_STATUS", payload=payload)


def _is_reindex(job: ClaimedJob) -> bool:
    return bool(job.payload.get("reindex"))


def _status_payload(job: ClaimedJob, request: IngestionRequest, status: str) -> dict[str, Any]:
    return {"workspaceId": str(job.workspace_id), "versionId": str(job.version_id),
            "status": status, "attempt": request.attempt}
