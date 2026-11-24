---
id: V2-24
title: "core-api: document metadata, flat categories/tags, department-based visibility"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: knowledge
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-12, V2-23]
blocks: [V2-16, V2-25, V2-26, V2-33, V2-36]
branch: "feat/knowledge-core-api-metadata-visibility"
assignee: pair
---

# TICKET V2-24: Document metadata and visibility

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
PRD-V2 FR-25 (the core-api part), FR-26, FR-27; ADR-007 §4.1, §4.4, §4.5. Replaces the general ACL `metadata.document_access_rules` with two scopes, `WORKSPACE | DEPARTMENTS`.

## 2. Acceptance criteria
- [x] `documents.visibility` defaults to `WORKSPACE`; `DEPARTMENTS` needs ≥ 1 department of the same workspace (`document_departments`, FK `RESTRICT`).
- [x] User-editable metadata (OWNER/ADMIN): title, short description, one category, many tags, language, visibility. System metadata is read-only. Every user-edited field records its source (`USER | SUGGESTED | SYSTEM`) so background suggestions do not overwrite it.
- [x] Flat per-workspace categories and tags; an ARCHIVED category cannot be newly assigned; deleting a category moves documents to "uncategorized" without affecting access.
- [x] Changing visibility: write the DB, call ai-service synchronously to update `rag.document_access`, retry through the outbox on failure; audit records the change.
- [x] Lists, search, detail, preview and download filtered by the ADR-007 §4.4 permissions; a MEMBER never sees the names of documents outside their access (404, not 403 with the name).
- [x] Download/preview through pre-signed URLs valid ≤ 5 minutes, issued only after the access check.
- [x] No re-embedding when editing title, description, category, tags or visibility.
- [x] `PUT /api/v1/documents/{id}/visibility` returns `{accessSync: APPLIED|PENDING}` per TECH-V2-core-api §2.3; the request is not blocked longer than ~2 s waiting for ai-service.
- [x] The ingest–access race (TECH-V2-DOCUMENT-ACCESS-SYNC §7.1): changing visibility while the document's `INGEST_REQUESTED` is still `PENDING` leaves ai-service with the latest scope and revision in the end (for example by updating the pending ingest event's `payload->'access'` in the same transaction); with an integration test.
- [x] (Moved from V2-12, review 2026-11-09) Every write/read statement in `DocumentRepository` repeats `workspace_id` in its `WHERE` (currently `setStatus`, `markReady`, `markFailed`, `resetForRetry`, `activate`, `setLatestVersion`, `updateMetadata`, `metaSources`, `softDelete`, `maxVersionNo` filter only by `id`), per the two-layer rule of RLS + application filtering.

## 3. Guide
- **Already there from V2-12, not redone:** the `VISIBLE` read filter in `DocumentRepository` (list/detail/download URL, `404`), the 5-minute `presign`, the `access` payload in `INGEST_REQUESTED`, the `ACCESS_UPDATED` branch of `HttpAiServiceClient`, `core.categories`, `core.document_departments`, the `*_source` columns. V2-24 wires the APIs, opens `DEPARTMENTS` (currently `requireWorkspaceVisibility` blocks it on upload) and adds tests.
- **Sync flow:** [TECH-V2-DOCUMENT-ACCESS-SYNC](../../../../architecture/data/document-access-sync.md); the contract is in TECH-V2-core-api §8. ai-service needs no changes.
- **Migration:** `core/V007` for `core.tags`, `core.document_tags` per TECH-V2-core-api §3.4 (RLS, grants), through the `flyway-migration` skill.
- **Files:** the documents/metadata modules in `services/core-api/`; migrations in `infrastructure/db/migrations/`.
- For reference: `services/metadata-service` (Category, Tag, DocumentMetadata), `frontend/web/app/admin/metadata/`. `document_access_rules` is not ported.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | The ADR-007 §4.4 permission matrix on the document service; metadata field sources; deleted/archived categories | `./mvnw test` |
| Integration | Visibility change → ai-service (mock) receives the update; ai-service error → outbox retry; pre-signed URL expiry | `./mvnw verify` |

## 5. Readiness review (2026-11-10)
The owner approved the start of implementation: V2-12, V2-23 `done`; the ai-service endpoints (`PUT /internal/document-access`, `DELETE /internal/documents`) and `access_filter.py` exist; TECH-V2-DOCUMENT-ACCESS-SYNC `approved`.

## 6. Results and acceptance
- **Done:** migration `core/V007` (`tags`, `document_tags`, RLS FORCE, grants); APIs `/api/v1/categories`, `GET /api/v1/tags`; `PATCH /documents/{id}` for `categoryId`, `tags[]` (source `USER`); upload accepts `visibility`, `departmentIds[]`, `title`, `categoryId`, `tags[]`; `PUT /documents/{id}/visibility` returns `{accessSync}`; updating `payload->'access'` of still-`PENDING` `INGEST_REQUESTED` events (the §7.1 race); `DocumentRepository` repeats `workspace_id` in every statement.
- **Scope sync:** the `ACCESS_UPDATED` event is written with a 60 s lease (the same mechanism as `claim_outbox_batch`) and sent directly on the request thread with a 2 s timeout right after commit; 2xx → `DELIVERED`/`APPLIED`, error or timeout → `PENDING` and the dispatcher resends when the lease expires or the backoff is due; 4xx other than 408/429 → `DEAD`.
- **Tests (2026-11-10):** `./mvnw verify` 102 unit + 113 integration, 0 failures; `check-migrations.ps1`, `check-docs.ps1` green. Main tests: `DocumentMetadataVisibilityIT`, `DocumentServiceTest`, `CategoryServiceTest`, `OutboxDispatcherIT`.
- **Deviations from TECH-V2-core-api:** empty, invalid, cross-workspace or `ARCHIVED` departments and an `ARCHIVED` category return `400` (`VALIDATION_FAILED`, `CATEGORY_ARCHIVED`); TECH §5.6 specifies no code. Categories and tags do not return `documentCount`.
- **Acceptance (owner, 2026-11-10):** `done`. The two services have not run together for real (ai-service mocked in the ITs); the frontend belongs to `V2-33`.
