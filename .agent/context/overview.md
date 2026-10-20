# Project Overview: SOPilot

> **Notice:** This project was originally codenamed *Poliwise* and has been unified under the product name **SOPilot**.
> PostgreSQL database `sopilot` uses the domain schemas `core`, `metadata`, `knowledge`, `conversation`, `analytics` (created in `infrastructure/init-db/000_bootstrap.sql`). There is no `poliwise_*` schema prefix. **DO NOT rename database schemas or prefix tables.**

SOPilot is an enterprise AI-powered Policy Knowledge Platform that enables employees to query internal policies, guidelines, and standard operating procedures using natural language, returning citations and relevant context.

---

## 1. Repository Structure

SOPilot is structured as a polyglot microservice monorepo:

- `frontend/web`: Next.js 16 App Router frontend (TypeScript, React 19, Tailwind CSS 4, Zustand)
- `services/api-gateway`: NestJS 11 API Gateway (single entry point for clients, port 3001)
- `services/auth-service`: Spring Boot 3 / Java 17 authentication & session management (port 8081)
- `services/user-service`: Spring Boot 3 / Java 17 user profiles & departments (port 8082)
- `services/knowledge-service`: Spring Boot 3 / Java 17 document lifecycle & versioning (port 8083)
- `services/metadata-service`: Spring Boot 3 / Java 17 categories, tags, access rules (port 8084)
- `services/feedback-service`: Spring Boot 3 / Java 17 analytics, feedback, audit logs (port 8085)
- `services/ai-qa-service`: FastAPI Python AI Q&A pipeline (RAG, intent, port 8086)
- `services/ingestion-service`: FastAPI Python document parsing, chunking, OCR, embeddings (port 8088)
- `infrastructure/init-db/`: PostgreSQL database initialization scripts
- `.agent/context/`: Comprehensive architectural decisions, service boundaries, and patterns
- `tests/`: Platform-wide E2E, cross-service integration, smoke tests, and fixtures
- `scripts/`: Development and diagnostic testing utilities
- `config/`: Local-only environment files such as `rabbitmq.env` (git-ignored, not in the repository)
- `docs/`: Specs (PRD, ADR, TECH), plans/tickets and reports; see `docs/README.md`

---

## 2. Service Responsibilities

### `auth-service` (Port 8081) — Schema `core`
- Login, registration, logout, session revocation.
- Access and refresh token lifecycle; token blacklist; login history.
- Default admin bootstrapping.
- Emits user-state events (`User.status.changed`, `User.revoked`).

### `user-service` (Port 8082) — Schema `core`
- User profile, department, and organization hierarchy.
- User account state management.
- Listens for and publishes user-related domain events.

### `knowledge-service` (Port 8083) — Schema `knowledge`
- Document lifecycle and physical file management (MinIO storage).
- Versioning, processing job tracking, status updates.
- Emits `Document.uploaded`, `Document.deleted`.

### `metadata-service` (Port 8084) — Schema `metadata`
- Document metadata, categories, tags, access policies.
- Controls document access levels (`PUBLIC`, `DEPARTMENT_ONLY`, `RESTRICTED`).

### `feedback-service` (Port 8085) — Schema `analytics`
- User feedback on answers (upvote/downvote, comments).
- Analytics aggregations, usage metrics, audit logging.
- Unanswered question tracking.

### `ai-qa-service` (Port 8086) — Schema `conversation`
- Retrieval-Augmented Generation (RAG) pipeline:
  - Layer 1: Prompt Guard & input toxicity checks
  - Layer 2: Intent classification
  - Layer 3: Hybrid retrieval (dense + sparse) & Reciprocal Rank Fusion (RRF)
  - Layer 4: Re-ranking
  - Layer 5: Response generation with citations (streaming support)
- Conversation session and message history.

### `ingestion-service` (Port 8088) — Stateless worker
- Document text extraction (PDF, DOCX, TXT), OCR for scanned files.
- Chunking, cleaning, metadata extraction.
- Dense embedding generation (BGE-M3).
- Orchestrated via RabbitMQ asynchronous task processing.

---

## 3. High-Level Architecture

### Frontend (`frontend/web`)
- **Framework**: Next.js 16 (App Router), React 19, TypeScript.
- **Key Entry Points**: `app/layout.tsx`, `app/page.tsx`.
- **Core Layers**:
  - `components/`: Modular UI (chat, documents, dashboard, shared layout).
  - `services/`: Specialized service layer (`auth.service.ts`, `ai.service.ts`, `document.service.ts`).
  - `lib/api.ts`: Centralized Axios API client with token refresh & interceptors.
  - `store/`: Zustand state management (`auth-store.ts`, `ui-store.ts`).
  - `types/` & `interfaces/`: Strongly-typed TypeScript contracts.

### API Gateway (`services/api-gateway`)
- Single entry point for all client requests (`http://localhost:3001`).
- Key Responsibilities:
  - JWT authentication & token validation.
  - Role-based access control (RBAC guards & decorators).
  - Rate limiting, circuit breakers, and timeout management.
  - Reverse proxying to downstream Spring Boot and FastAPI microservices.
  - Trace ID injection, request logging, and normalized response formats.

### Spring Microservices (`services/*-service`)
- **Stack**: Spring Boot 3.4.x, Java 17, Spring Data JPA, PostgreSQL.
- **Communication**: OpenFeign (synchronous internal HTTP), Spring AMQP / RabbitMQ (asynchronous events).
- **Package Layout**: `config`, `controller`, `dto`, `entity`, `enums`, `exception`, `mapper`, `repository`, `service`.

---

## 4. Database Ownership Boundaries

SOPilot enforces strict schema isolation within the `sopilot` PostgreSQL database:

| Schema | Owner Service | Port | Key Entities |
|---|---|---|---|
| `core` | `auth-service` & `user-service` | 8081 / 8082 | Users, Profiles, Departments, Sessions, Login History, Blacklist, Employee Roster |
| `knowledge` | `knowledge-service` | 8083 | Documents, Versions, Processing Jobs |
| `metadata` | `metadata-service` | 8084 | Categories, Tags, Access Rules |
| `analytics` | `feedback-service` | 8085 | Feedback, Aggregated Metrics, Audit Logs |
| `conversation` | `ai-qa-service` | 8086 | Conversations, Messages, Citations |

> [!CRITICAL]
> Services MUST NOT query or modify tables outside their assigned schema directly. Cross-service data requirements are handled via REST APIs (through Feign / HTTP) or RabbitMQ events.

---

## 5. Event-Driven Integration (RabbitMQ)

RabbitMQ facilitates decoupled, asynchronous event workflows.

- **Configuration**: Main exchange `sopilot.events`; auth/user still declare legacy `poliwise.auth.exchange` and `poliwise.user.exchange`. Local broker settings may live in the git-ignored `config/rabbitmq.env`. Event contracts: `service-boundaries/events.md`.
- **Core Events**:
  - `User.status.changed`: Account activation/suspension.
  - `User.revoked`: Session termination across services.
  - `Document.uploaded`: Initiates parsing, OCR, and embedding pipelines.
  - `Document.deleted`: Purges chunks and embeddings.
  - `Unanswered.question`: Logged by `ai-qa-service` for admin review in `feedback-service`.

---

## 6. Role-Based Access Control (RBAC)

| Role | Permissions & Capabilities |
|---|---|
| `USER` | Query policies via AI Q&A, view public/department documents, submit feedback, manage own profile. |
| `MANAGER` | All `USER` capabilities + view department analytics, export reports, review unanswered questions. |
| `ADMIN` | Full administrative capabilities: upload & manage policies, configure access rules, manage users & roles, view audit logs. |

---

## 7. Docker Topology & Ports

All services are orchestrated via `docker-compose.yml` on the shared `sopilot-network` bridge network. Only `frontend` and `api-gateway` publish ports to the host; the other ports below are container ports reachable inside the network.

| Container | Port | Purpose |
|---|---|---|
| `postgres` | 5432 | Primary PostgreSQL database with pgvector extension |
| `rabbitmq` | 5672, 15672 | Message broker and management UI |
| `minio` | 9000, 9001 | S3-compatible object storage |
| `redis` | 6379 | Cache used by `api-gateway` and `ai-qa-service` |
| `auth-service` | 8081 | Authentication microservice |
| `user-service` | 8082 | User & department microservice |
| `knowledge-service` | 8083 | Knowledge & document lifecycle microservice |
| `metadata-service` | 8084 | Metadata & access control microservice |
| `feedback-service` | 8085 | Feedback & analytics microservice |
| `ai-qa-service` | 8086 | AI Q&A & conversation microservice |
| `ingestion-service` | 8088 | Ingestion & embedding worker |
| `api-gateway` | 3001 (published) | API Gateway |
| `frontend` | 3000 (published) | Next.js web application |

