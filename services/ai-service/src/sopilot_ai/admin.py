"""Operator commands: ``python -m sopilot_ai.admin reindex [--all] [--dry-run]``.

``reindex`` re-ingests every active version whose chunks were embedded by another
``(embedding_model, embedding_revision)`` than the active one, or extracted with another
``normalizer_version`` (TECH-V2-ai-service §5.2, §6.4 D2(e)). ``--all`` re-ingests every active
version, which is required after a BM25 tokenizer or chunking change. The worker does the work;
this command only queues the jobs.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.config import Settings, get_settings
from sopilot_ai.db.engine import ensure_selector_loop_policy, make_engine, system_tx, tenant_tx
from sopilot_ai.db.repositories import reindex as repo
from sopilot_ai.docproc.render import NORMALIZER_VERSION
from sopilot_ai.providers.embedding import resolve_revision
from sopilot_ai.providers.registry import ModelsConfig

log = structlog.get_logger(__name__)


def active_embedding(settings: Settings) -> tuple[str, str]:
    """``(model, revision)`` written on new chunks, without loading the model."""
    spec = ModelsConfig.load(settings.models_config).embedding()
    return spec.model, resolve_revision(spec, settings.profile)


async def stale_count(engine: AsyncEngine, model: str, revision: str) -> int:
    async with system_tx(engine) as conn:
        return len(await repo.stale_versions(conn, model=model, revision=revision,
                                             normalizer_version=NORMALIZER_VERSION))


async def reindex(engine: AsyncEngine, model: str, revision: str, *, every: bool = False,
                  dry_run: bool = False) -> tuple[int, int]:
    """Returns ``(stale versions found, jobs queued)``."""
    async with system_tx(engine) as conn:
        stale = await repo.stale_versions(conn, model=model, revision=revision,
                                          normalizer_version=NORMALIZER_VERSION, every=every)
    queued = 0
    for v in stale:
        if dry_run:
            log.info("reindex_candidate", document_id=str(v.document_id),
                     version_id=str(v.version_id))
            continue
        async with tenant_tx(engine, v.workspace_id) as conn:
            if await repo.requeue_version(conn, v.version_id):
                queued += 1
            else:
                log.warning("reindex_skipped_no_finished_job", version_id=str(v.version_id))
    return len(stale), queued


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m sopilot_ai.admin")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("reindex", help="queue active versions for ingestion again")
    cmd.add_argument("--all", action="store_true", help="every active version, not only stale")
    cmd.add_argument("--dry-run", action="store_true", help="list, do not queue")
    args = parser.parse_args(argv)

    settings = get_settings()
    model, revision = active_embedding(settings)
    engine = make_engine(settings.db_url.get_secret_value(), pool_size=1)
    try:
        found, queued = await reindex(engine, model, revision, every=args.all,
                                      dry_run=args.dry_run)
    finally:
        await engine.dispose()
    log.info("reindex_done", model=model, revision=revision, found=found, queued=queued,
             dry_run=args.dry_run)
    return 0


def main() -> None:
    ensure_selector_loop_policy()
    sys.exit(asyncio.run(_main(sys.argv[1:])))


if __name__ == "__main__":
    main()
