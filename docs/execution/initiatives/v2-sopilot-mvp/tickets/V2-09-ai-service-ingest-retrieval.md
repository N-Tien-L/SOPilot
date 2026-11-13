---
id: V2-09
title: "ai-service: ingest worker, embedding, hybrid retrieval, RLS, 4 score types, provider interface"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-06, V2-08, V2-20, V2-21, V2-22]
blocks: [V2-10, V2-12, V2-14, V2-25, V2-35]
branch: "feat/ai-qa-v2-ingest-retrieval"
assignee: pair
---

# TICKET V2-09: ai-service (ingest + retrieval)

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
The new service `services/ai-service` (FastAPI) replaces `ai-qa-service` and `ingestion-service`. Port the embedding and the hybrid SQL selectively; fix R1–R5 and AUDIT §4.2. Extraction and chunking are split into V2-20 and V2-22 (owner decision 2026-10-19 per [AUDIT-ingestion-sop-data](../../../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md)); this ticket wires them into the worker and stores the chunks.

## 2. Acceptance criteria
- [x] The ingest worker calls extraction (V2-20) and chunking (V2-22); chunks store `workspace_id`, `document_id`, `page`, character positions and the heading path.
- [x] `embedding_provider/model/dim/revision` stored per chunk; cache key `(model, revision, sha256)`; no `tiktoken` cutting.
- [x] `rag` schema migration for the tables of TECH-V2-ai-service §3.1–§3.4 plus `outbox_events`, `processed_requests` (§3.5) and the function `rag.claim_ingestion_job()`; the `suggestion_*` tables left to `V2-25`, `message_feedback`/`knowledge_gap_status` to `V2-13`.
- [x] The `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`) and `RerankProvider` (`local` | `none`) interfaces; `models.yaml` is the only place models are declared. `EmbeddingProvider.tokenizer()` returns `V2-22`'s `docproc.tokens.HFTokenizer` (TECH-V2-ai-service §1.1), never a second tokenizer.
- [x] Hybrid dense + BM25 + RRF, **every query filters `workspace_id`** (parameterized, no f-strings) with RLS on.
- [x] The `rag.document_access` table (ADR-007 §4.5) and an internal endpoint for core-api to update it; dense and BM25 filter by `wrole`/`wdept` **before** `LIMIT k`; documents without an access row are never retrieved.
- [x] `dense_score`, `bm25_score`, `fusion_score`, `rerank_score` stored separately; rerank runs before the threshold; a threshold per mode.
- [x] Changed 2026-10-21 (TECH-V2-ai-service §5.4, §6.4, §3.3, §3.4): the worker passes `title` and `extracted_meta.docCode` (V2-21) to the chunker; writes `chunks.lang` from language detection; `fusion` has `cross_lingual_bm25_factor` (default `1.0`, a test that `1.0` gives plain RRF results); the migration has `chunks.lang` and `messages.context_sources` (the column used in `V2-10`).
- [x] Changed 2026-10-21 (end-to-end audit by query type, owner decisions D2/D11; TECH-V2-ai-service §3.4, §6.3, §6.4): (a) the `rag.messages` migration includes `refusal_reason`, `route jsonb`, `rewrite_status`, `checks jsonb` and the `refusal_reason` CHECK right away (in this ticket's migration, **no** second migration); (b) the BM25 tokenizer adds diacritic-free `~` terms for words with diacritics, `lexical_len` counts only original terms, and diacritic-free queries use both original and `~` terms; (c) `qa/doc_code.py` detects document codes in questions and `retrieval.doc_code_boost` is added to the `fusion_score` of chunks whose `extracted_meta.docCode` matches; (d) the `hybrid` gate always has a `dense_score`: candidates with only a BM25 score get their cosine computed directly (`fusion.gate_score`, shared with `eval/`), and `retrieval_results.dense_score` is complete for all 25 candidates; (e) the admin command `python -m sopilot_ai.admin reindex` (when `normalizer_version`, the embedding model or the tokenizer changes) and a startup check: chunks of active versions not matching the enabled `(embedding_model, embedding_revision)` → `ERROR` log, `/health` returns `degraded`. Tests: a BM25-only candidate at the gate gives the same score in harness and service; "quy trinh mua hang" matches "quy trình mua hàng" while English questions are unchanged; `QT-MH-01` is boosted; `reindex` brings mismatched versions back in line.
- [x] The worker handles jobs durably: it scans pending jobs at startup; statuses `PROCESSING → READY | FAILED`, retryable. Error classification per TECH-V2-ai-service §5.1: transient errors are retried automatically with `run_after` backoff and no intermediate `FAILED`; deterministic errors are `FAILED` immediately with the right code; when attempts run out the last code is kept (`RETRY_EXHAUSTED` only without a code).
- [x] Retries (owner decision 2026-10-21, TECH-V2-ai-service §8): `POST /internal/ingestions` with the same `versionId` and a greater `attempt` moves a `FAILED` job back to `QUEUED` and reruns it exactly once; resending the same `attempt` (or a running/`DONE` job) creates no job. Integration tests for all three branches.
- [x] `extracted_documents` (canonical Markdown, `page_index`, `warnings`, `boilerplate`, `extracted_meta` = the SOP metadata from `clean/metadata.py` per document version, `normalizer_version`) written only in the activation transaction (§5.6); the `READY` callback sends `warningCodes` and `attempt`.
- [x] `GET /ai/v1/documents/{id}/versions/{versionId}/content` per TECH-V2-ai-service §7.3 (used by FR-14 and FR-31): `404` for inactive, `FAILED`, deleted or out-of-access versions (FR-25); while a replacement is processing it returns the active version; UTF-16 offsets correct for strings with non-BMP characters. The FR-19/FR-29 tests cover this endpoint.
- [x] Retrieval results on the V2-06 corpus match the `eval/` harness within the stated tolerance (TECH-V2-ai-service §6.5: mean top-10 Jaccard ≥ 95%), with the harness on the same `docproc` chunker and configuration; `eval/` switches to importing `sopilot_ai.retrieval.lexical` and `fusion` in the same change. The tokenizer (`~` terms) and the `dense_score` gate were already in the harness from `V2-07`, so this is only an import switch, without changing the RQ numbers.

## 3. Guide
- **Files:** `services/ai-service/` (CREATE), using the V2-20/V2-22 modules, with reference to `services/ai-qa-service/src/db/repositories/chunk_repo.py`.
- The chunk migration lives in `infrastructure/db/migrations/` (V2-08).

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | RRF, mocked providers, per-mode thresholds | `uv run pytest tests/unit` |
| Integration | Real Postgres: ingest → retrieval, RLS blocks without `workspace_id` | `uv run pytest tests/integration` |

```powershell
./scripts/validate-build.ps1 -Scope ai        # scope added by V2-20
./scripts/run-tests.ps1 -Scope ai-service -Type all
```

## 5. Progress

**Step 1/2 (2026-11-04, accepted by the owner):** the owner settled the decisions outside the TECH design: `definer_*` policies only for `sopilot_migrator` so SECURITY DEFINER functions run under `FORCE ROW LEVEL SECURITY`; docproc's `TEXT` → `PROSE` (PROSE family) or `SECTION`; an old version finishing after a newer version is `DONE` gets its job `CANCELLED`; new env vars `SOPILOT_PROFILE`, `SOPILOT_S3_SECURE`, `SOPILOT_INGEST_LEASE_SECONDS`, `SOPILOT_INGEST_BACKOFF_SECONDS`, `SOPILOT_WORKER_POLL_SECONDS`, `SOPILOT_OUTBOX_*`; `suggestion_jobs` not created yet (V2-25). Content: migration `rag/V003__rag_tables.sql` (every table of §3.1–§3.5, §7.6, RLS, `claim_ingestion_job`, `claim_outbox_batch`, `stale_active_versions`); `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`) reading `config/models.yaml`, `tokenizer()` returning `docproc.tokens.HFTokenizer`; `retrieval/lexical.py` (`~` terms, `lexical_len`); the ingest worker wiring `docproc` (extract → clean → render → family → chunk, passing `title` and `docCode`), language detection, embedding with a `(model, revision, sha256)` cache, the §5.6 activation transaction, §5.1 error classification, outbox + dispatcher; `POST /internal/ingestions` (internal token, `Idempotency-Key`, retries by `attempt`). Tests: 23 unit + 15 integration (real pgvector Postgres, role `sopilot_ai_app`).

**Step 2/2 (2026-11-04, accepted by the owner 2026-11-05):** `retrieval/access_filter.py` (a single `allowed_cte()`, parameterized, explicit `workspace_id` next to RLS); `retrieval/search.py` (dense with `hnsw.iterative_scan`, BM25 in SQL with `N`/`df`/`avgdl` over the readable set, direct cosine for BM25-only candidates, docCode, text for rerank, all filtered before `LIMIT`); `retrieval/fusion.py` (RRF, `cross_lingual_bm25_factor`, `doc_code_boost`, `gate_score`, per-mode thresholds); `retrieval/retriever.py` (4 separate scores, rerank before the gate, `hybrid` always with a `dense_score`); `qa/doc_code.py`; `RerankProvider` (`local` | `none`); `retrieval_results.save`; `PUT /internal/document-access/{id}`, `DELETE /internal/documents/{id}`; `GET /ai/v1/documents/{id}/versions/{versionId}/content` (RS256 JWT through core-api's JWKS, a generic `404`, UTF-16 offsets); `/health` `degraded` with an `ERROR` log on model/normalizer mismatch; `python -m sopilot_ai.admin reindex [--all] [--dry-run]` (the `reindex` job sends no callback). `eval/` imports the tokenizer, `BM25` and fusion from `sopilot_ai.retrieval` (harness behaviour unchanged, compared function by function). Tests: 24 unit + 12 new integration (178 in total). §6.5 comparison (`sopilot_eval.service_parity`, sop-main 105 questions, 575 docproc chunks, bge-m3): mean top-10 Jaccard dense 1.000, bm25 0.993, hybrid 0.995, hybrid-xl0.3 0.997; every difference is at rank 10, from tie-breaking (identical chunks in two documents) or BM25 candidates with score 0 that the harness still ranks.

**Acceptance 2026-11-05:** the owner accepted step 2/2 and set `done`. The ai-service code (`services/ai-service/`, migration `rag/V003__rag_tables.sql`) and the `eval/` import change were **not committed** at acceptance time; committed on branch `feat/ai-qa-v2-ingest-retrieval`.
