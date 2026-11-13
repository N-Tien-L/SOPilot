---
id: ADR-004
title: "V2: two backend services (core-api Spring Boot + ai-service FastAPI); drop the gateway, RabbitMQ and Redis"
status: approved
created: 2026-10-16
updated: 2026-11-13
author: "Owner"
refs: [docs/product/prd-v2-sopilot-mvp.md]
deciders: ["Owner"]
amends: []
supersedes: [ADR-002]
superseded_by: ""
---

# ADR-004: Two backend services; drop the gateway, RabbitMQ and Redis

> **Status:** `approved` (2026-10-20) | **Proposed:** `2026-10-16` | **Decider:** `Owner`
>
> On approval this ADR replaced ADR-002 (gateway as reverse proxy). ADR-002's "the backend verifies the Google ID token itself" part is kept, in core-api.
>
> Translated from Vietnamese on 2026-11-13; section numbers are stable (cited by code).

---

## 1. Context and the decision to make
- The system had 8 services (a NestJS gateway, 5 Spring Boot services, 2 FastAPI services) plus RabbitMQ, Redis and MinIO, about 40 thousand lines of backend code. It cannot be hosted for free and one person cannot maintain it.
- PRD-V2 requires a target cost of 0 USD/month, while the project must show both Java (SWE) and Python (AIE) skills.
- Every service must be a boundary with a real reason (different language, load or lifecycle), not a split for the sake of having many services.

## 2. Evaluation criteria
1. Operating cost and the number of processes to run.
2. Clear data ownership, no cross-schema writes.
3. The effort of one person in one semester.
4. Value for the CV and the research report.
5. The ability to test tenant isolation end to end.

## 3. Options considered

### Option 1: keep the 8 microservices, only cut features
- **(+)** Little rewriting.
- **(−)** Still needs RabbitMQ/Redis/gateway; cost and operational complexity do not drop; the tenancy problem has to be fixed in 6 services.

### Option 2: FastAPI + Supabase (Auth, Postgres, Storage)
- **(+)** Cheapest and fastest; RLS built in.
- **(−)** No Java left; the owner ruled this option out on 2026-10-16.

### Option 3: core-api (Spring Boot) + ai-service (FastAPI), each a modular monolith
- **(+)** Boundaries follow language and load type: business/transactions in Java, ML/RAG in Python. Only 2 application processes.
- **(+)** Design patterns worth showing on a CV: RS256 JWT + JWKS between services, an outbox for ingest work, a Postgres `FOR UPDATE SKIP LOCKED` queue, RLS.
- **(−)** Most of the Java code has to be rewritten for the workspace model.

## 4. Decision and rationale
- **Chosen option:** **Option 3.**

### 4.1 Components
| Component | Technology | Responsibility | Schema owned |
|---|---|---|---|
| `frontend/web` | Next.js | UI | — |
| `services/core-api` | Spring Boot 3.x | Google login, users, workspaces, memberships, invitations, documents (metadata + files), audit, document quota | `core` |
| `services/ai-service` | FastAPI | Ingest worker, hybrid retrieval, SSE answer generation, conversations, feedback, knowledge gaps, question quota, eval harness | `rag` |
| PostgreSQL 16 + pgvector | — | Storage | `core`, `rag` |
| S3-compatible object storage | Pinned MinIO version (local), R2/B2 (deployment) | Original files | a single bucket, configured through env |

> **Changed 2026-10-20 (owner, TECH-V2 Q1):** feedback and knowledge gaps (FR-16, FR-17) moved from core-api to ai-service, because questions, answers, citations and refusal flags all live in `rag`; keeping them in core-api would mean copying question content over the outbox. Quotas (FR-09) are currently off.

Choice of embedding, LLM, reranker and storage, and how each environment runs (local eval, deployment): [ADR-006](adr-006-free-tier-providers-and-environments.md).

There is no gateway, RabbitMQ or Redis.

### 4.2 Authentication between components
- core-api issues **RS256** access tokens and publishes its public key at `/.well-known/jwks.json`. ai-service verifies tokens with that JWKS (cached) without calling core-api on every request.
- Internal calls between the two services use `/internal/**` endpoints, authenticated with a service token configured through env, and are never exposed publicly.
- The browser sees **one origin**: a reverse proxy (or Next.js rewrites) routes `/api/**` to core-api and `/ai/**` to ai-service. The exact mechanism is fixed in the TECH design.

### 4.3 Ingest without a message broker
1. core-api stores the file in storage and writes `core.documents` with status `UPLOADED` in one transaction.
2. A scheduler in core-api (outbox) sends `UPLOADED` documents to ai-service's `POST /internal/ingestions`. ai-service writes the job to `rag.ingestion_jobs` (idempotent on `document_id` + `checksum`) and returns `202`.
3. ai-service's worker takes the job with `SELECT ... FOR UPDATE SKIP LOCKED` and, when done, calls core-api's `PATCH /internal/documents/{id}/status`.
4. Deleting a document goes through the same outbox mechanism to delete its chunks.

Each service writes only its own schema. ai-service does not read `core`; everything it needs (`workspace_id`, object key, checksum) travels in the job.

### 4.4 Migrations and data
- V2 starts from a **new database**; there is no production data to keep. The new migrations live in `infrastructure/db/migrations/`, one version chain per schema, run by Flyway (a one-shot container in compose and in CI).
- `infrastructure/init-db/` stays untouched until the old services are removed. A local volume reset runs only when the owner explicitly asks.

### 4.5 Transition inside the repo
- Write the new services in `services/core-api` and `services/ai-service`, next to the old ones. Old code is only a reference to port from; it is not developed further.
- Port selectively: Google token verification and `(issuer, sub)` binding (ADR-003), refresh-token rotation, extraction/chunking/embedding, the hybrid retrieval SQL, the frontend chat components.
- Every ported part needs its own tests in the new service that run without the old services (port the old tests if any, then adapt them to the V2 contract). Record the port source (old file) in the ticket so V2-17 knows which parts have been replaced.
- During the transition the two stacks are fully separate: the V2 compose has its own project name, containers and volumes, and non-overlapping host ports; only one stack runs at a time (V2-08). The last working V1 build is tagged `v1-final` before the frontend moves to V2 (V2-15).
- When V2 reaches parity with PRD-V2, remove the old services in a separate commit (git history keeps them), then update `CLAUDE.md`, `.claude/`, the scripts and the architecture docs.

## 5. Impact and consequences
- **Positive:** only 2 application processes; deployable to one free VM; simple data boundaries; each service has its own story for the CV.
- **Trade-offs:**
  - Ingest emits no immediate event: latency depends on the scheduler period (a few seconds).
  - The gateway features (role-based rate limiting, circuit breaker) are lost; quotas move into core-api and ai-service.
  - Most of the Java is rewritten; the old code coexists for a while, and `check-conventions.ps1`/`run-tests.ps1` need new scopes.
- **Next actions (historical, all done):**
  - Write `TECH-V2-core-api` and `TECH-V2-ai-service` (DDL, API, sequences).
  - Add the `core-api` and `ai-service` scopes to `validate-build.ps1` and `run-tests.ps1`.
  - On approval: set ADR-002 to `superseded` and update the agent instructions (then `AGENTS.md`, now `CLAUDE.md`: topology table, migration rules).
