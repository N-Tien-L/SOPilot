---
title: "SOPilot V2 system overview"
status: approved
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
affected_services: [core-api, ai-service, web, infra, eval]
affected_schemas: [core, rag]
refs:
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/architecture/components/core-api.md
  - docs/architecture/components/ai-service.md
---

# SOPilot V2 system overview

> **Implementation status:** core-api, ai-service, both schemas and the eval harness exist; the frontend is still V1-wired until V2-15; apps run from source (`docker-compose.v2.yml` runs only infrastructure until V2-16). The frozen V1 stack (eight services, gateway, RabbitMQ, Redis, `infrastructure/init-db/`) is described in [archive/v1-context](../archive/v1-context/architecture/system-overview.md) and removed by V2-17.

## 1. Components and ownership

| Component | Path | Owns |
|---|---|---|
| core-api (Spring Boot, Java 21, JdbcTemplate) | `services/core-api` | Schema `core`: users, workspaces, members, departments, documents/versions, quota, audit, outbox; all S3 writes. [Design](components/core-api.md) |
| ai-service (FastAPI, Python, SQLAlchemy async) | `services/ai-service` | Schema `rag`: extraction, chunks, embeddings, retrieval, conversations, jobs; S3 read-only. [Design](components/ai-service.md) |
| frontend (Next.js) | `frontend/web` | UI. [Current state](components/frontend.md) |
| Postgres 16 + pgvector | `infrastructure/db` | Flyway chains `migrations/core` and `migrations/rag`; roles `sopilot_migrator` (owner), `sopilot_core_app`, `sopilot_ai_app` (NOBYPASSRLS, DML on their own schema only) |
| MinIO | `infrastructure/storage` | Binary documents, bucket `sopilot-v2-documents` |
| eval harness | `eval/` | RQ1–RQ5 retrieval and answer metrics; imports `sopilot_ai.retrieval` |
| Modal endpoint | `infrastructure/modal/` | Self-hosted answer LLM and the GPU reranker (ADR-006 §4.4, V2-34, V2-35) |

Each service writes only its own schema; there is no cross-schema SQL (ADR-004). Schemas: [core](data/core-schema.md), [rag](data/rag-schema.md).

## 2. Communication

- **core-api → ai-service:** a transactional outbox (`core.outbox_events`), sent after commit by `OutboxDispatcher`: `INGEST_REQUESTED`, `ACCESS_UPDATED`, `DOCUMENT_DELETED`. See [document access sync](data/document-access-sync.md).
- **ai-service → core-api:** `/internal/**` callbacks with `X-Internal-Token` (version status, metadata suggestions), from ai-service's own outbox.
- **Browser → both services:** the core-api RS256 access token (claims `wid`, `wrole`, `wdept`; ≤ 15 min); ai-service verifies it through `/.well-known/jwks.json`. See [HTTP conventions](api/http-conventions.md) and [identity and access](domain/identity-and-access.md).

## 3. Main flows

1. **Sign-in:** Google ID token (or dev login in `local`/`test`) → JIT user and PERSONAL workspace → access token + refresh cookie.
2. **Upload:** core-api validates type/size/SHA-256/quota, stores the file in MinIO, creates the version and an `INGEST_REQUESTED` event in one transaction.
3. **Ingest:** the ai-service worker claims the job, extracts with Docling (ADR-008), cleans, renders canonical Markdown, chunks, embeds (bge-m3), and activates the version in one transaction; it reports `READY`/`FAILED` back and queues metadata suggestions.
4. **Question:** rules guard → optional semantic router → retrieval (dense/BM25/hybrid, optional rerank) filtered by workspace and read access before `LIMIT` → refusal gate → generation on Modal → citations checked → answer streamed over SSE.
5. **Access change:** core-api bumps `access_revision` and emits `ACCESS_UPDATED`; ai-service applies only newer revisions.

## 4. Tenant isolation (FR-19)

Two layers, both mandatory: Postgres RLS on `<schema>.current_workspace()` (bound per transaction by `TenantTx` / `tenant_tx`), **and** an explicit `workspace_id` filter in every query. Department read access (FR-29) is a third check on top. CI runs the DB suite, a negative control with RLS disabled, the `TenantIsolation*IT` suites and the department authorization suites (`tenant-isolation.yml`); see [the V2-14 report](../quality/test-reports/audit-v2-14-tenant-isolation-rq4-2026-11-06.md).

## 5. Environments

Local only, no deployment (ADR-006). `docker-compose.v2.yml` (project `sopilot-v2`) runs Postgres on `127.0.0.1:55432`, MinIO on `59000/59001` and one-shot Flyway/MinIO init jobs. Run commands are in `CLAUDE.md` and the service READMEs.
