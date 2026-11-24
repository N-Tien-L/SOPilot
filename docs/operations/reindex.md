---
title: "Re-index documents after a model or chunking change"
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
---

# Re-index documents after a model or chunking change

**When:** `GET /health` on ai-service reports `{"status":"degraded","staleVersions":N}`; the embedding model or revision in `services/ai-service/config/models.yaml` changed; the normalizer version changed; or the BM25 tokenizer or chunking changed (use `--all`). **Risk:** re-ingestion rewrites the chunks and embeddings of active versions and loads the embedding model. The command only queues jobs; the ingest worker does the work. Design: TECH-V2-ai-service §3.3 and §5.2 ([ai-service design](../architecture/components/ai-service.md)).

## Steps

Prerequisites: infrastructure up and the worker running ([local development](local-development.md)). The command needs the ai-service environment loaded in the shell (at least `SOPILOT_DB_URL` and `SOPILOT_INTERNAL_TOKEN`; settings are required at startup).

1. List what would be queued, without queuing:

   ```powershell
   cd services/ai-service
   $env:PYTHONPATH = "src"; uv run python -m sopilot_ai.admin reindex --dry-run
   ```

   Each candidate is logged as `reindex_candidate`.
2. Queue the stale versions (embedded by another `(model, revision)`, or extracted with another normalizer version):

   ```powershell
   $env:PYTHONPATH = "src"; uv run python -m sopilot_ai.admin reindex
   ```

   Add `--all` to queue every active version. The command ends with a `reindex_done` log line giving `found` and `queued`. A version without a finished job is skipped and logged as `reindex_skipped_no_finished_job`.
3. Let the worker run the jobs. Pin `EMBEDDING_REVISION` first if the results will be evaluated (empty is accepted in profile `local`, a startup error in profile `eval`).

## Verify

`GET http://localhost:8000/health` returns `{"status":"ok"}` once no stale versions remain. Job progress is in `rag.ingestion_jobs` (`QUEUED`/`RUNNING`); inspect it with read-only SQL as described in [troubleshooting](troubleshooting.md).

## Roll back

There is no undo. Revert the config or code change that made the versions stale and run the command again; the previous model must be available to the worker. Do not edit chunks by hand.
