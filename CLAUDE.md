# CLAUDE.md

Guidance for AI coding agents working in the Poliwise repository.

## 1) Mandatory Working Rules

- Always check architecture and boundary context before implementing features, changing database interaction, or touching service contracts.
- Source of truth for architecture and ownership:
  - `contexts/architecture/`
  - `contexts/frontend/`
  - `contexts/patterns/`
  - `contexts/service-boundaries/`
  - `contexts/database/`
  - `contexts/authorization/`
  - `contexts/development/`
- Living documentation rule:
  - If you add or change REST endpoints, DB schema, RBAC roles, or service responsibilities, update related files in `contexts/`.
  - Briefly summarize which context files were updated.
  - If context docs are outdated or missing, propose updates proactively.
- Verify real implementation before extending features. Some parts may still be scaffold or placeholder code.
- Ignore build artifacts such as `target/` and `node_modules/`.

## 2) Repository Overview

Poliwise is a multi-service monorepo with:

- `frontend/web`: Next.js 16 App Router frontend (TypeScript)
- `services/api-gateway`: NestJS 11 API gateway (single client entry point)
- `services/*-service`: Spring Boot 3 / Java 17 microservices
- `services/ai-qa-service`: FastAPI AI Q&A pipeline
- `services/ingestion-service`: FastAPI document processing/embedding
- `infrastructure/init-db/`: SQL initialization scripts
- `contexts/`: Architecture, patterns, and development documentation
- `scripts/`: Utility and testing scripts
- `reports/`: Project reports, audits, and class deliverables
- `config/`: Shared environment/config files (including RabbitMQ)
- `docs/`: Product and architecture notes

## 3) Common Commands

### Frontend (`frontend/web`)

- Install deps: `pnpm install`
- Dev server: `pnpm dev`
- Build: `pnpm build`
- Start production: `pnpm start`
- Lint: `pnpm lint`
- Test: `pnpm test`

### API Gateway (`services/api-gateway`)

- Install deps: `pnpm install`
- Start (watch): `pnpm run start:dev`
- Start (once): `pnpm run start`
- Build: `pnpm run build`
- Lint: `pnpm run lint`
- Test: `pnpm test`
- E2E test: `pnpm run test:e2e`

### Spring Boot Services (`services/<service-name>`)

- Run locally: `./mvnw spring-boot:run`
- Build jar: `./mvnw package`
- Run all tests: `./mvnw test`
- Run one test class: `./mvnw -Dtest=ClassName test`
- Run one test method: `./mvnw -Dtest=ClassName#methodName test`

### Full Stack (Docker)

- Start all services: `docker compose up`

### AI Q&A Service (`services/ai-qa-service`)

- Install deps: `uv sync` (or `pip install -r requirements.txt`)
- Run: `uv run uvicorn src.main:app --reload --port 8086`
- Run tests: `uv run pytest`

### Ingestion Service (`services/ingestion-service`)

- Install deps: `uv sync` (or `pip install -r requirements.txt`)
- Run: `uv run uvicorn src.main:app --reload --port 8088`
- Run tests: `uv run pytest`

## 4) High-Level Architecture

### Frontend: `frontend/web`

- Next.js 16 App Router app.
- Main entry points:
  - `app/layout.tsx`
  - `app/page.tsx`
- Core layers:
  - `components/` for shared UI/layout
  - `services/` for API calls (`auth.service.ts`, `ai.service.ts`, etc.)
  - `store/` for Zustand state
  - `interfaces/`, `types/` for shared contracts

### API Gateway: `services/api-gateway`

Primary responsibilities:

- JWT validation and auth flow
- RBAC enforcement (guards + decorators)
- Rate limiting and timeout handling
- Circuit breaker for downstream resilience
- Request proxying to microservices
- Trace ID propagation and request logging
- Response normalization and exception filtering
- Security headers and CORS
- Service health checks

Important source folders:

- `src/auth/`
- `src/proxy/`
- `src/health/`
- `src/common/` (guards, decorators, filters, interceptors, DTOs)
- `src/config/`

### Spring Microservices: `services/*-service`

Shared stack and pattern:

- Spring Boot 3.x + Java 17
- JPA repositories + PostgreSQL
- Spring Security, Validation, OpenFeign, RabbitMQ, Actuator
- Typical package layout: `config`, `controller`, `dto`, `entity`, `enums`, `exception`, `mapper`, `repository`, `service`

## 5) Service Responsibilities

### `auth-service` (8081) - schema `poliwise_auth`

- Login/register/logout/session revocation
- Access and refresh token lifecycle
- Login history and token blacklist
- Default admin bootstrap
- Emits user-state events

### `user-service` (8082) - schema `poliwise_user`

- User profile and department domain
- Account state management
- Emits user-state events

### `knowledge-service` (8083) - schema `poliwise_knowledge`

- Document lifecycle and processing pipeline
- Versioning and processing job tracking

### `metadata-service` (8084) - schema `poliwise_metadata`

- Document metadata, categories, tags
- Document access rules and lifecycle status

### `feedback-service` (8085) - schema `poliwise_analytics`

- Feedback and usage analytics
- Aggregations, audit logs, reporting, unanswered questions

### `ai-qa-service` (8086) - schema `conversation`

- RAG pipeline: intent classification, retrieval, reranking
- Streaming answer generation
- Conversation and message history

### `ingestion-service` (8088) - no dedicated schema

- Document chunking, text extraction, OCR
- Embedding generation (BGE-M3)
- Processing job orchestration via RabbitMQ

## 6) Database Ownership Boundaries

Strong ownership per service:

- `poliwise_auth` -> `auth-service`
- `poliwise_user` -> `user-service`
- `poliwise_knowledge` -> `knowledge-service`
- `poliwise_metadata` -> `metadata-service`
- `poliwise_analytics` -> `feedback-service`
- `conversation` -> `ai-qa-service`

Do not bypass ownership boundaries without explicit architecture updates.

## 7) Event-Driven Integration

RabbitMQ is used for cross-service communication.

Core events include:

- `User.status.changed`
- `User.revoked`
- `Document.uploaded`
- `Document.deleted`
- `Unanswered.question`

Shared RabbitMQ configuration lives in `config/rabbitmq.env`.

## 8) RBAC Model

Roles and capabilities:

- `USER`: AI Q&A, own profile, feedback
- `MANAGER`: USER capabilities + analytics dashboard + report export + unanswered questions view
- `ADMIN`: MANAGER capabilities + document upload + metadata management + user management

Reference document: `docs/allow_per_role.md`.

## 9) Docker Topology

Main local ports:

- Postgres: 5432
- RabbitMQ: 5672, management 15672
- Auth service: 8081
- User service: 8082
- Knowledge service: 8083
- Metadata service: 8084
- Feedback service: 8085
- AI Q&A service: 8086
- Ingestion service: 8088
- API gateway: 3001
- Frontend: 3000

All services run on shared `poliwise-network` with persistent data volumes.

## 10) Recommended Implementation Flow

When adding a feature end-to-end:

1. Update service API/domain logic first.
2. Update API gateway routes/guards/contracts.
3. Update frontend services/components.
4. Run lint/tests.
5. Update relevant `contexts/` documentation.

## 11) Notes About AI Policy Files

- Expected policy files may be referenced in docs (`.cursor/rules/`, `.github/copilot-instructions.md`).
- If these files are absent in the current checkout, continue with repository conventions and documented contexts.
