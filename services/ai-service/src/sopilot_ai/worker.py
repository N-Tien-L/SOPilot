"""Ingestion worker process: ``python -m sopilot_ai.worker`` (TECH-V2-ai-service §1, §2.1, §3.2).

On start it drains every due job left in the queue before waiting (FR-08, ADR-006 B1 constraint
3); then it wakes on ``NOTIFY rag_jobs`` or every ``SOPILOT_WORKER_POLL_SECONDS``. After each job
the outbox is pushed right away, and it is swept again on every wake-up.
"""
from __future__ import annotations

import asyncio
import contextlib
import signal

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.admin import stale_count
from sopilot_ai.config import Settings, get_settings
from sopilot_ai.db.engine import ensure_selector_loop_policy, make_engine, system_tx
from sopilot_ai.db.repositories import jobs
from sopilot_ai.docproc import CleanConfig
from sopilot_ai.ingest.handler import IngestDeps, handle_job
from sopilot_ai.ingest.storage import MinioObjectStore
from sopilot_ai.outbox.dispatcher import OutboxDispatcher
from sopilot_ai.providers.embedding import build_embedding_provider
from sopilot_ai.providers.registry import ModelsConfig

log = structlog.get_logger(__name__)

CHANNEL = "rag_jobs"


async def drain(deps: IngestDeps, lease_seconds: int, dispatcher: OutboxDispatcher | None,
                stop: asyncio.Event | None = None) -> int:
    """Run due jobs until none is left; returns how many were handled."""
    handled = 0
    while stop is None or not stop.is_set():
        async with system_tx(deps.engine) as conn:
            job = await jobs.claim(conn, lease_seconds)
        if job is None:
            break
        await handle_job(job, deps)
        handled += 1
        if dispatcher is not None:
            await dispatcher.dispatch_due()
    return handled


async def _listen(dsn: str, wake: asyncio.Event, stop: asyncio.Event) -> None:
    """LISTEN on a dedicated autocommit connection; reconnects after errors."""
    import psycopg

    while not stop.is_set():
        try:
            async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
                await conn.execute(f"LISTEN {CHANNEL}")
                async for _ in conn.notifies():
                    wake.set()
                    if stop.is_set():
                        return
        except Exception as exc:  # noqa: BLE001 - polling continues while the listener is down
            log.warning("worker_listen_error", error=type(exc).__name__)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=5)


def _psycopg_dsn(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


async def run(settings: Settings, engine: AsyncEngine | None = None) -> None:
    config = ModelsConfig.load(settings.models_config)
    embedder = build_embedding_provider(config, settings.profile)
    tokenizer = embedder.tokenizer()
    chunk_config = config.chunking()
    engine = engine or make_engine(settings.db_url.get_secret_value())
    deps = IngestDeps(
        engine=engine,
        store=MinioObjectStore(settings.s3_endpoint, settings.s3_access_key.get_secret_value(),
                               settings.s3_secret_key.get_secret_value(), settings.s3_bucket,
                               settings.s3_secure, settings.s3_region),
        embedder=embedder,
        tokenizer=tokenizer,
        chunk_config=chunk_config,
        clean_config=CleanConfig.from_env(),
        max_attempts=settings.ingest_max_attempts,
        backoff_base_seconds=settings.ingest_backoff_base_seconds,
    )
    stop, wake = asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows has no add_signal_handler
            loop.add_signal_handler(sig, stop.set)

    async with httpx.AsyncClient(base_url=settings.core_base_url,
                                 timeout=settings.outbox_http_timeout_seconds) as client:
        dispatcher = OutboxDispatcher(engine, client, settings.internal_token.get_secret_value(),
                                      max_attempts=settings.outbox_max_attempts)
        listener = asyncio.create_task(
            _listen(_psycopg_dsn(settings.db_url.get_secret_value()), wake, stop))
        log.info("worker_started", model=embedder.model, revision=embedder.revision)
        stale = await stale_count(engine, embedder.model, embedder.revision)
        if stale:
            log.error("index_out_of_date", stale_versions=stale,
                      hint="run python -m sopilot_ai.admin reindex")
        try:
            while not stop.is_set():
                wake.clear()
                try:
                    await drain(deps, settings.ingest_lease_seconds, dispatcher, stop)
                    await dispatcher.dispatch_due()
                except Exception:  # noqa: BLE001 - a lost DB connection must not end the worker
                    log.exception("worker_iteration_failed")
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(wake.wait(), timeout=settings.worker_poll_seconds)
        finally:
            stop.set()
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener
            await engine.dispose()


def main() -> None:
    ensure_selector_loop_policy()
    asyncio.run(run(get_settings()))


if __name__ == "__main__":
    main()
