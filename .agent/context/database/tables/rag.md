# Schema `rag` (V2, ai-service)

Source of truth: `infrastructure/db/migrations/rag/V003__rag_tables.sql` (V2-09) and
`docs/02-architecture/designs/TECH-V2-ai-service.md` §3. Only `sopilot_ai_app` has DML here.

## Tenant isolation

Every table with `workspace_id` has `ENABLE` + `FORCE ROW LEVEL SECURITY` and policy
`tenant_isolation` (`workspace_id = rag.current_workspace()`). ai-service sets
`app.workspace_id` / `app.user_id` with `set_config(..., true)` at the start of each transaction
(`sopilot_ai.db.engine.tenant_tx`). No tenant set = no rows (fail closed).

Tables **without** `workspace_id` and RLS, by design: `embedding_cache` (vectors keyed by content
hash only), `processed_requests` (idempotency keys), `system_usage` (daily counts).

## Tables

| Table | Purpose | Written by |
|---|---|---|
| `document_access` | Read scope per document (`visibility`, `department_ids`, `access_revision`), `active_version_id`, title at ingest | `POST /internal/ingestions`, `PUT /internal/document-access/{id}`, activation; row removed by `DELETE /internal/documents/{id}` |
| `ingestion_jobs` | Durable job queue, one row per `version_id`; `request_attempt` (core-api `attempt`), `attempts`, `lease_until`, `run_after`, `failure_code`, `stage_timings` | internal API, worker |
| `extracted_documents` | Canonical Markdown, cleaned structure, `page_index`, `warnings`, `boilerplate`, `extracted_meta`, `normalizer_version`, `doc_family`, `language` | worker, only in the activation transaction |
| `chunks` | Chunk text, `index_text`, offsets on the canonical Markdown, pages, `section_path`, `lang`, `vector(1024)` + `embedding_provider/model/dim/revision`, `lexical_len` | worker |
| `chunk_terms` | BM25 index: `(chunk_id, term) -> tf`, including `~` folded terms | worker |
| `embedding_cache` | `(model, revision, content_sha256) -> vector` | worker |
| `retrieval_results` | All `rerank_pool` candidates of a question with `dense_score`, `bm25_score`, `fusion_score`, `rerank_score` kept apart, `in_context` for the hit chunks | `sopilot_ai.db.repositories.retrieval_results.save` (called by the Q&A pipeline, V2-10) |
| `conversations`, `messages`, `message_citations`, `guard_events`, `usage_counters`, `system_usage` | Q&A (V2-10); `messages` has `refusal_reason`, `route`, `rewrite_status`, `checks`, `context_sources`. One turn writes a USER and an ASSISTANT row in one transaction (`conversations/repository.py`); counters only when a quota is on (`quota/counters.py`) | used since V2-10 milestone 3 |
| `message_feedback`, `knowledge_gap_status` | FR-16/17 (V2-13) | not yet used |
| `suggestion_jobs`, `suggestion_cache` | Metadata suggestions (V2-25) | not yet used |
| `outbox_events` | `VERSION_STATUS` / `SUGGESTIONS_READY` callbacks to core-api | worker; dispatcher marks `DELIVERED`/`DEAD` |
| `processed_requests` | `Idempotency-Key` of `/internal/**` | internal API |

`chunks.chunk_type` is `SECTION | PROCEDURE_STEP | TABLE | PROSE`; docproc's `TEXT` maps to
`PROSE` in the PROSE family and `SECTION` otherwise (`sopilot_ai.ingest.pipeline.chunk_type`).

## Cross-workspace helpers (SECURITY DEFINER, owner `sopilot_migrator`, EXECUTE for `sopilot_ai_app`)

| Function | Use |
|---|---|
| `rag.claim_ingestion_job(lease_seconds)` | One due job of any workspace (`QUEUED` and `run_after <= now()`, or `RUNNING` with expired lease); sets `RUNNING`, lease, `attempts + 1` |
| `rag.claim_outbox_batch(limit, lease_seconds)` | Due `PENDING` events; pushes `next_attempt_at` forward as a lease |
| `rag.stale_active_versions(model, revision, normalizer_version, all)` | Active versions to ingest again (startup check, `admin reindex`) |

Because `FORCE ROW LEVEL SECURITY` also binds the table owner, these functions rely on extra
policies granted `TO sopilot_migrator` only (`definer_jobs`, `definer_outbox`, `definer_read` on
`document_access`, `chunks`, `extracted_documents`). Application roles never match them.

## Rules

- No FK to `core`; `document_id`, `version_id`, `user_id`, `department_id` come from core-api.
- `NOTIFY rag_jobs` wakes the worker when a job is created or re-queued.
- Every read of chunks or extracted documents starts from
  `sopilot_ai.retrieval.access_filter.allowed_cte()` (TECH §6.1): `deleted_at IS NULL`,
  `active_version_id` match, `wrole` OWNER/ADMIN or `WORKSPACE` visibility or `wdept` in
  `department_ids`, plus `workspace_id = :wid` next to RLS. The filter sits in `WHERE`/`JOIN`, so it
  applies before `LIMIT` (FR-25). Used by dense, BM25, the direct cosine of BM25-only candidates,
  document codes, reranker texts and `GET /ai/v1/documents/{id}/versions/{versionId}/content`.
- Dense also filters `embedding_model/revision` = active model. BM25 statistics (`N`, `df`,
  `avgdl`) are computed over the chunks the asker may read (`retrieval.search`).
- `DELETE /internal/documents/{id}?workspaceId=` sets `deleted_at`, then deletes jobs, chunks
  (terms cascade), `extracted_documents`, `suggestion_jobs` and the access row in one
  transaction; `message_citations` stay.
- Startup check: the API and the worker log `ERROR index_out_of_date` when
  `stale_active_versions` returns rows for the active `(model, revision)` and the current
  `NORMALIZER_VERSION`; `/health` then answers `{"status": "degraded", "staleVersions": n}`.
  `python -m sopilot_ai.admin reindex [--all] [--dry-run]` re-queues those versions' jobs with
  payload `reindex: true` (no status callback to core-api; old chunks stay until activation).
