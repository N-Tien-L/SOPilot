---
id: V2-12
title: "core-api: documents, upload, outbox, document quota, safe replacement, audit log"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: knowledge
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-11]
blocks: [V2-13, V2-14, V2-16, V2-24, V2-31, V2-32]
branch: "feat/knowledge-core-api-documents"
assignee: pair
---

# TICKET V2-12: core-api (documents)

> Translated from Vietnamese on 2026-11-13; content unchanged. Context-doc paths under `.agent/context/` are as they were at the time.

## 1. Context & goal
FR-06, 07, 09, 20, 30, 31 (the core-api part). Replaces knowledge-service and RabbitMQ with an outbox + HTTP calls to ai-service. Changed 2026-10-21 per [AUDIT-markdown-normalization](../../../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md): TXT dropped, document quota on by default, the replacement rule while processing, retries carry `attempt`.

## 2. Acceptance criteria
- [x] DOCX deferred until after the MVP (owner decision 2026-10-20, FR-06): upload returns `415`, creates no job; tells the user to export a PDF with a text layer, no server-side conversion.
- [x] Upload accepts only PDFs with a text layer and MD (UTF-8) ≤ 20 MB; `.txt`, DOCX, images → `415` with no S3 write, no version/job, and a guiding message (TXT → `.md`, DOCX → PDF); MD that is not UTF-8 → `415 INVALID_ENCODING`; SHA-256 duplicates blocked within the workspace; only OWNER/ADMIN upload/delete, every member views/downloads (FR-06).
- [x] Lifecycle `UPLOADED → PROCESSING → READY | FAILED`, retry, replacement (old chunks deleted after the new version is `READY`), deleting a document deletes the file and chunks (FR-07).
- [x] Duplicates are judged only by SHA-256 between different documents in the workspace, reporting the existing document's name; no semantic dedup (AUDIT-ingestion-sop-data step 9).
- [x] Replacements follow all 5 branches of TECH-V2-core-api §3.3, one test each: processing + same bytes → `200` returning the processing version; processing + different bytes → `409 VERSION_IN_PROGRESS`; same SHA-256 as the current `READY` version → `409 DOCUMENT_UNCHANGED`, no version/outbox/job (owner decision 2026-10-20, PRD-V2 FR-07; replacing the old criterion that allowed creating a new version identical to the old one); a duplicate of another document → `409 DUPLICATE_DOCUMENT`; different bytes → a new version. Files with different bytes are not refused for being similar.
- [x] Safe replacement: while the new version processes and when it is `FAILED`, `current_version_id` stays and the document remains queryable on the old version; when the new version is `READY`, every older version (including `FAILED`) becomes `SUPERSEDED`.
- [x] Retry: `POST /retry` only when the latest version is `FAILED`, increments `attempt`, sends `attempt` in the ingest payload; two consecutive calls create only one outbox event (`409 VERSION_NOT_FAILED` the second time); callbacks with an old `attempt` are ignored. Retrying one file does not touch other documents.
- [x] Editing title/description/category/tags creates no `INGEST_REQUESTED` outbox event (a test counts outbox rows). (title/description/language: tested by counting outbox rows; category/tags belong to V2-24)
- [x] `Document` returns `currentVersion.warningCodes` and `latestVersion {id, versionNo, status, failureCode, failureMessage}` (TECH-V2-core-api §5.5) for the FR-31 view; `failureMessage` is a fixed sentence per code that leaks no internal error.
- [x] A new document has `WORKSPACE` scope by default and an access row in ai-service before `READY` (the `DEPARTMENTS` scope is V2-24). (The ingest payload carries `access` `WORKSPACE`, `accessRevision` 1; `DEPARTMENTS` is refused with `400` until V2-24. Real run 2026-11-07: `rag.document_access` has `visibility=WORKSPACE`, `access_revision=1`, `active_version_id` set after `READY`; the order of writing the access row relative to `READY` was not measured separately)
- [x] The outbox pushes to ai-service over HTTP (to wake it up), with retries; ai-service scans pending jobs at startup (FR-08).
- [x] A per-workspace document quota configured through env, **50 documents / 200 MB by default** (owner decision 2026-10-21, replacing the 2026-10-20 default of off), `0` = off. Checked in the transaction under a per-workspace advisory lock: a workspace with 48 documents receiving 10 concurrent uploads gives exactly 2 successes and 8 `409 QUOTA_EXCEEDED` with `{limit, used}`, no orphan S3 objects after the janitor; replacing a version does not increase the document count; `0` tested too. The question quota belongs to ai-service (V2-10), not here (FR-09).
- [x] Audit log: sign-in, member/role changes, upload/delete; the OWNER views the workspace's log (FR-20). (role changes not yet, as there is no role-change endpoint until V2-30)
- [x] Every table has `workspace_id` + RLS; queries also filter in the application layer.
- [x] Files stored through the standard S3 API, bucket/endpoint from env (avoiding bucket-name drift as before).

## 3. Guide
- **Files:** the documents/outbox/audit modules of `services/core-api/`; migrations in `infrastructure/db/migrations/`.
- Reference source: `services/knowledge-service`.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | quota (default 50/200 MB, `0`), SHA-256 duplicates, the 5 replacement branches, retry and `attempt`, PDF/MD magic bytes, TXT/DOCX refused, role permissions | `./mvnw test` |
| Integration (concurrency) | 10 parallel uploads hitting the quota; 2 parallel uploads with the same SHA-256 | `./mvnw verify` |
| Integration | upload → outbox → ai-service (mock) → READY; deletion cleans up chunks | `./mvnw verify` |

## 5. Implementation evidence (2026-11-06, accepted 2026-11-09)

The owner accepted on 2026-11-09 and set `done`. Code at commit `4113f63` (S3 region fix in `e96599c`), merged into `develop` through [PR #5](https://github.com/N-Tien-L/SOPilot/pull/5). The 5 TECH deviations below were approved and recorded in TECH-V2-core-api §13. The "Not done / not checked" items were accepted as open and belong to the tickets named.

- **Recheck at acceptance (2026-11-09):** `cd services/core-api && ./mvnw -B verify` → 73 unit + 78 integration, 0 failures (including `DocumentLifecycleIT` 18, `DocumentConcurrencyIT` 7, `DocumentQuotaIT` 3, `DocumentQuotaDisabledIT` 1, `OutboxDispatcherIT` 10, `S3StorageClientIT` 5, `TenantIsolationApiIT` 8). Reread `DocumentService`, `VersionStatusService`, `DocumentOutboxHooks`, `OutboxDispatcher`, `HttpAiServiceClient`: a consistent lock order (document row, SHA-256, quota), old `attempt` callbacks ignored, logs record only the error class name and the HTTP code.
- **Review remark (not blocking):** some write statements in `DocumentRepository` (`setStatus`, `markReady`, `markFailed`, `resetForRetry`, `activate`, `setLatestVersion`, `updateMetadata`, `metaSources`, `softDelete`, `maxVersionNo`) filter only by `id`, without repeating `workspace_id`. Nothing leaks today because every call runs after `lockDocument(workspace_id, id)` in the same `TenantTx` and RLS stays on; `workspace_id` should be added to follow the two-layer rule (CLAUDE.md constraint 4); added as a criterion of V2-24 (the ticket changing this repository).

- **Code:** `services/core-api/src/main/java/com/sopilot/core/{document,outbox,storage,audit,security,tenancy}/`; migration `infrastructure/db/migrations/core/V005__documents_outbox_audit.sql` (`categories`, `documents`, `document_versions`, `document_departments`, `outbox_events`, an append-only `audit_logs`, `claim_outbox_batch`, `referenced_object_keys`). `JwtAuthFilter`/`InternalTokenFilter`/`TenantTx` are the base of every endpoint (V2-11 only issued tokens).
- **Commands:** `cd services/core-api && ./mvnw verify` → 66 unit + 70 integration, 0 failures (41 + 14 before). V2-12 alone: `UploadValidatorTest` (8), `AccessTokenVerifierTest` (7), `HttpAiServiceClientTest` (4, a real HTTP server), `DocumentLifecycleIT` (18), `DocumentConcurrencyIT` (7), `DocumentQuotaIT` (3), `DocumentQuotaDisabledIT` (1), `OutboxDispatcherIT` (10), `S3StorageClientIT` (5, real MinIO `RELEASE.2024-05-10T01-41-38Z`, pre-signed URLs downloadable, UTF-8 file names in `Content-Disposition`).
- **Quota:** a workspace with 48 documents receiving 10 concurrent uploads → exactly 2 successes, 8 `409 QUOTA_EXCEEDED`, 50 objects in storage, `StorageJanitor.sweep(0)` deletes 0 objects. 4 parallel uploads of the same bytes → 1 document, 3 `DUPLICATE_DOCUMENT`. 2 parallel retries → 1 outbox event. 3 parallel replacements with different bytes → 1 version, 2 `VERSION_IN_PROGRESS`. The byte quota, replacements not increasing the document count, soft-deleted documents not counted, `0` disabling the quota: all tested.
- **Contract with ai-service:** the `INGEST_REQUESTED` payload (taken from the tests) passes `sopilot_ai.ingest.schemas.IngestionRequest.model_validate`; the `X-Internal-Token` header and `Idempotency-Key` = the outbox id; the `PATCH .../status` callback accepts exactly the fields ai-service sends (`workspaceId`, `status`, `attempt`, `embedding`, `extracted`, `warningCodes`, `failureCode`); a non-ISO `extracted.effectiveDate` is ignored instead of `400` (ai-service dead-letters every `4xx`).
- **Deviations from TECH-V2-core-api:** (1) the S3 PUT runs **at the end** of the transaction, just before commit, instead of before every DB step (§2.2): conflicts (duplicate, quota, in progress) never touch storage; an orphan object remains only when the commit fails after the PUT, cleaned by `StorageJanitor` (1-hour age). The advisory lock is held during the PUT, acceptable at this scale. (2) `TenantTx` wraps each transaction instead of a `TransactionSynchronizationManager` listener (§4.3). (3) `QUOTA_EXCEEDED` returns `409` per the ticket and §3.3 (§5.0 says `422`). (4) `failure_message` stores a fixed Vietnamese sentence per code (not per `Accept-Language`). (5) `PATCH /documents/{id}` edits title/description/language; category/tags/visibility are V2-24.
- **Real run (2026-11-07):** Postgres + MinIO from `docker-compose.v2.yml` (Flyway applied core V001–V005, rag V001–V003), core-api (`mvnw spring-boot:run`, profile `local`) + the ai-service API + worker run by hand on Windows; a `dev-login` scenario with two users in two workspaces, 19 steps. Results: MD `READY` (first time 132 s because bge-m3 loaded cold), PDF through Docling `READY` after 10 s; duplicate SHA-256 `409 DUPLICATE_DOCUMENT`; same bytes as the current version `409 DOCUMENT_UNCHANGED`; different bytes → new version `READY`, old version `SUPERSEDED`; TXT and non-UTF-8 MD `415`; `POST /retry` on a `FAILED` version → `200`, second time `409 VERSION_NOT_FAILED`, one new outbox event, result `READY`; the signed URL returns the right bytes; the core-api token verified by ai-service through JWKS (`/ai/v1/documents/{id}/versions/{vid}/content` 200 for the owner, `404` for another workspace, `401` without a token); deleting a document → 0 chunks, 0 extractions, 0 access rows, the S3 object deleted, `DOCUMENT_DELETED` `DELIVERED`. **Bug found and fixed:** the ai-service worker could not read MinIO (every job `RETRY_EXHAUSTED`) because minio-py calls `GetBucketLocation` while the read-only policy `sopilot-ai-ro` has only `s3:GetObject`; V2-09's mocked tests did not catch it. Fixed with `SOPILOT_S3_REGION` (default `us-east-1`) passed to `Minio(region=...)`, test `tests/unit/test_object_store.py`. Windows note: `uvicorn` uses `ProactorEventLoop`, so the ai-service API fails with async psycopg; run it with a `SelectorEventLoop` wrapper (the worker sets the policy itself). LLM/Q&A not run (V2-10).
- **Not done / not checked:** Q&A across both services (V2-10); `ACCESS_UPDATED` and the `DEPARTMENTS` scope (V2-24); `PUT /internal/documents/{id}/suggestions` (V2-25; ai-service sends it only when `suggest.enabled`, currently always `false`); refresh/switch (V2-29); frontend (V2-31, V2-32).
- **Docs:** `.agent/context/{database/schema.md, database/tables/core.md, service-boundaries/api-contracts.md, authorization/v2-core-identity.md, README.md}`, `.env.example`, `services/core-api/README.md`.
