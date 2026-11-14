---
title: "HTTP conventions and endpoint map (V2)"
status: approved
created: 2026-11-04
updated: 2026-11-13
author: "Owner"
affected_services: [core-api, ai-service, web]
affected_schemas: []
refs:
  - docs/architecture/components/core-api.md
  - docs/architecture/components/ai-service.md
  - docs/architecture/data/document-access-sync.md
---

# HTTP conventions and endpoint map (V2)

> **Implementation status:** reflects V2-09 to V2-13, V2-23 to V2-25, V2-29, V2-30 and V2-36. Moved from the V2 header of the former agent context `service-boundaries/api-contracts.md` on 2026-11-13; the rest of that file describes V1 (gateway, `ApiResponse` with `success`) and is archived at [v1-context/service-boundaries/api-contracts.md](../../archive/v1-context/service-boundaries/api-contracts.md). The detailed contracts are TECH-V2-core-api §5 and §8 and TECH-V2-ai-service §7; this page is the map.

## 1. Shared rules

- Every `/api/v1/**` (core-api) and `/ai/v1/**` (ai-service) route needs `Authorization: Bearer <access token>`, except `/api/v1/auth/**` and `/.well-known/jwks.json`. ai-service verifies the core-api token through JWKS. Token claims: see [identity and access](../domain/identity-and-access.md).
- The workspace and role come from the token only, never from the path or body. Another workspace's object, or a document outside the caller's read access, is `404`.
- Client-facing error messages are fixed sentences with a stable code; never `e.getMessage()` (A8).
- `/internal/**` are service-to-service callbacks guarded by `X-Internal-Token` (constant-time compare). They are not called by the browser.

## 2. core-api (`/api/v1`)

- **Envelope:** success `{"data": ..., "traceId": "..."}`; lists `{"data": [...], "page": {"cursor", "hasMore"}, "traceId"}`; error `{"error": {"code", "message", "details"}, "traceId"}`. `X-Trace-Id` is accepted (8–64 `[A-Za-z0-9-]`) or generated, and echoed.
- **Common codes:** `400 VALIDATION_FAILED` (details list field names only), `401 INVALID_GOOGLE_TOKEN`, `401 UNAUTHENTICATED`, `401 MEMBERSHIP_LOST`, `403 MEMBERSHIP_SUSPENDED`, `403 NOT_PUBLISHER`, `404 NOT_FOUND`, `405 METHOD_NOT_ALLOWED`, `415 UNSUPPORTED_MEDIA_TYPE`, `500 INTERNAL_ERROR`.
- **Auth and sessions:** `POST /auth/google/nonce`, `POST /auth/google`, `POST /auth/dev-login` (`local`/`test` only), `POST /auth/refresh`, `POST /auth/logout`, `GET /.well-known/jwks.json`.
- **Workspaces:** list, create TEAM, switch, `/workspaces/current` read/rename/soft delete.
- **Departments:** `GET/POST /departments`, `PATCH/DELETE /departments/{id}` (`409 DEPARTMENT_NAME_TAKEN`, `409 DEPARTMENT_IN_USE` with counts); publishers `PUT|DELETE /departments/{id}/publisher`, `/publishers/workspace`, `GET /publishers`.
- **Members and invitations:** `GET /members`, `GET /members/me` (with `publisherOf`), `PATCH /members/{userId}` (profile, department, role), `POST /members/{userId}/suspend|reactivate`, `DELETE /members/{userId}`, `POST /members/leave` (`409 LAST_OWNER`, `409 EMPLOYEE_CODE_TAKEN`, `409 DEPARTMENT_ARCHIVED`); `GET/POST /invitations`, `DELETE /invitations/{id}` (revoke), `POST /invitations/accept`.
- **Documents:** `POST /documents` (multipart `file`, 20 MB, PDF or Markdown only: `415 UNSUPPORTED_TYPE|INVALID_ENCODING`, `413 FILE_TOO_LARGE`, `409 DUPLICATE_DOCUMENT|QUOTA_EXCEEDED`), `POST /documents/{id}/versions` (`409 VERSION_IN_PROGRESS|DOCUMENT_UNCHANGED`), `POST /documents/{id}/retry` (`409 VERSION_NOT_FAILED`), `GET /documents` (cursor page), `GET /documents/{id}`, `PATCH /documents/{id}`, `PUT /documents/{id}/visibility`, `PUT /documents/{id}/ownership` (OWNER), `GET /documents/{id}/download-url|versions`, `DELETE /documents/{id}`; categories and tags.
- **Audit:** `GET /audit-logs` (OWNER).
- **Internal callbacks from ai-service:** `PATCH /internal/documents/{id}/versions/{versionId}/status` (TECH-V2-core-api §8.2), `PUT /internal/documents/{id}/suggestions` (V2-25).

Note: the quota error is `409 QUOTA_EXCEEDED` in code while TECH-V2-core-api §5.0 lists `422`; code wins (recorded in the TECH document).

## 3. ai-service (`/ai/v1`)

- **Envelope:** plain JSON, not the core-api `{"data", "traceId"}` envelope. Errors use FastAPI's default body `{"detail": "<fixed sentence>"}` with no stable `code` field (`401` `authentication required`, `403`, `404`, `503` `question answering is not available`); only the SSE `error` event carries a code. `503` when the LLM endpoint or embedding model is not configured (the first question builds them).
- **Health:** `GET /health` (no token) returns `{"status": "ok"}`, or `{"status": "degraded", "staleVersions": n}` when chunks of active versions were embedded by another model or revision (TECH-V2-ai-service §5.2).
- **Content:** `GET /documents/{id}/versions/{versionId}/content` (the canonical Markdown of a `READY` version the caller may read).
- **Conversations:** `POST /conversations/{id|new}/messages` body `{content, lang?}` answers with `text/event-stream` (events `meta`, `delta`, `replace`, `refusal`, `citations`, `done`, `error`; TECH-V2-ai-service §7.2; `error` codes `QUOTA_EXCEEDED`, `LLM_UNAVAILABLE`, `INTERNAL_ERROR`, fixed text). `GET /conversations`, `GET /conversations/{id}`: an answer generated from a document no longer readable (any source in its LLM context or any citation) comes back as `{hidden: true, reason: ACCESS_REVOKED|DOCUMENT_DELETED}`. `PATCH /conversations/{id}` (title), `DELETE /conversations/{id}` (soft). Another user's or workspace's conversation is `404`.
- **Feedback and knowledge gaps** (V2-13, TECH-V2-ai-service §7.6): `PUT /messages/{id}/feedback` `{vote: -1|1, comment?}` → `204` (conversation owner, `ASSISTANT` message only, one vote per user, else `404`); `GET /knowledge-gaps?status=open|resolved&limit&offset` (OWNER/ADMIN, MEMBER `403`; PII-masked question, no asker identity); `POST /knowledge-gaps/{messageId}/resolve` `{note?}` (OWNER/ADMIN, idempotent, `404` if not a gap).
- **Internal from core-api** (outbox): `POST /internal/ingestions`, `PUT /internal/document-access/{id}`, `DELETE /internal/documents/{id}?workspaceId=`; see [document access sync](../data/document-access-sync.md).
