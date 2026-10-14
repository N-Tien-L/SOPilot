# SOPilot Developer & AI Agent Handbook (`AGENTS.md`)

> **Notice:** This project was originally codenamed *Poliwise* and has been unified under the product name **SOPilot**.
> PostgreSQL database is named `sopilot` (user: `sopilot`). The application schemas are strictly partitioned by domain: `core`, `metadata`, `knowledge`, `conversation`, `analytics`.

---

## 🧭 System Topology & Architecture

| Service | Port | Tech Stack | Database Schema / Store | Primary Responsibility |
|---|---|---|---|---|
| **Frontend** | `3000` | Next.js 16, React 19, TypeScript, Tailwind 4, Zustand | Browser / Local Storage | Employee Q&A, Admin Document & User Management UI |
| **API Gateway** | `3001` | NestJS 11, TypeScript | In-memory / Reverse Proxy | Single Client Entry Point, JWT verification, RBAC guards, Trace ID |
| **auth-service** | `8081` | Spring Boot 3.4, Java 17 | `core` | Authentication, Token issuance/revocation, Google OAuth JIT |
| **user-service** | `8082` | Spring Boot 3.4, Java 17 | `core` | User profiles, Departments, Pre-provisioned Employee Roster |
| **knowledge-service** | `8083` | Spring Boot 3.4, Java 17 | `knowledge` + MinIO | Document lifecycle, Versioning, Upload/Delete events |
| **metadata-service** | `8084` | Spring Boot 3.4, Java 17 | `metadata` | Document tags, Categories, Department visibility rules |
| **feedback-service** | `8085` | Spring Boot 3.4, Java 17 | `analytics` | Feedback upvotes/downvotes, Analytics metrics, Unanswered questions |
| **ai-qa-service** | `8086` | FastAPI, Python 3.12+ | `conversation` | Hybrid RAG (pgvector dense + BM25 sparse RRF), Streaming synthesis |
| **ingestion-service** | `8088` | FastAPI, Python 3.12+ | Stateless (RabbitMQ + MinIO) | Document text extraction (PDF/DOCX), Chunking, Jina AI embedding |
| **PostgreSQL** | `5432` | Postgres 16 + pgvector | Database: `sopilot` (schemas: `core`, `metadata`, `knowledge`, `conversation`, `analytics`) | Primary structured and vector storage |
| **RabbitMQ** | `5672` / `15672` | AMQP 0-9-1 | Exchange: `sopilot.events` | Asynchronous inter-service event publishing and ingestion |
| **MinIO** | `9000` / `9001` | S3 API compatible | Bucket: `sopilot-documents` | Binary document storage (`staging`, `documents` buckets) |

---

## 🛡️ Critical Safety Guardrails (MANDATORY)

1. **Volume & Database Protection**:
   - Schema modifications must be written as numbered additive scripts in `infrastructure/init-db/`.
   - To reset/re-bootstrap local database cleanly: use `./infrastructure/init-db/reset-and-bootstrap.ps1`.
   - **NEVER** execute destructive DDL (`DROP DATABASE`, `DROP SCHEMA`, `TRUNCATE TABLE`) on active production databases.
2. **File System Scoping**:
   - All operations must strictly remain inside this workspace. Never modify or delete files outside the repository root.
   - **NEVER** run recursive wildcard deletions (`rm -rf *`, `Remove-Item * -Recurse`). Specify exact file targets.
3. **Secrets & Environment Isolation**:
   - **NEVER** commit `.env` or hardcode secrets/API keys (`GROQ_API_KEY`, `EMBEDDING_API_KEY`, DB passwords, JWT secrets).
   - Use `.env.example` with dummy values for documentation.
4. **Git Discipline**:
   - **NEVER** commit directly to `main`. Develop on `develop` or short-lived feature branches (`feat/*`, `fix/*`).
   - Follow Conventional Commits: `<type>(<scope>): <summary>`.

---

## 📜 Working Rules for AI Agents

1. **Check Boundaries First**: Consult `.agent/context/` before changing data models, inter-service contracts, or routing.
2. **Progressive Skill Loading**:
   - Requirements analysis & PRD: consult `.agent/skills/analyze-requirements/SKILL.md`
   - Architecture & Technical Design: consult `.agent/skills/design-architecture/SKILL.md`
   - Planning & Decomposition: consult `.agent/skills/plan-and-decompose/SKILL.md`
   - Ticket implementation: consult `.agent/skills/execute-ticket/SKILL.md`
   - Writing tests (Unit/Integration/E2E): consult `.agent/skills/write-test/SKILL.md`
   - Running tests & verification: consult `.agent/skills/run-test/SKILL.md`
   - Quality, coverage & audit analysis: consult `.agent/skills/analyze-quality/SKILL.md`
   - Spring Boot backend work: consult `.agent/skills/springboot-backend/SKILL.md`
   - Python FastAPI work: consult `.agent/skills/python-backend/SKILL.md`
   - NestJS API Gateway work: consult `.agent/skills/nestjs-gateway/SKILL.md`
   - Next.js Web Frontend work: consult `.agent/skills/nextjs-frontend/SKILL.md`
3. **Living Documentation**: If you alter endpoints, schemas, or events, update the corresponding markdown file in `.agent/context/`.

---

## 🛠️ Central Scripts & Common Commands

Run all scripts from repository root:

```powershell
# Pre-commit automated checklist
./scripts/pre-commit-check.ps1

# Run tests by scope (scopes: auth-service, user-service, knowledge-service, metadata-service, feedback-service, ai-qa-service, ingestion-service, api-gateway, frontend)
./scripts/run-tests.ps1 -Scope <service-name> -Type <all|unit|integration>

# Validate build & lint for specific scope
./scripts/validate-build.ps1 -Scope <auth|user|knowledge|metadata|feedback|ai-qa|ingestion|gateway|web>

# Check git conventions & debug statement pollution
./scripts/check-conventions.ps1 -Scope <web|gateway|auth|user|...>

# Check health of all running services & infrastructure
./scripts/check-services.ps1

# Trace request routing path through API Gateway
./scripts/trace-request.ps1 -Endpoint "/api/v1/users/profile"
```

### Direct Service Commands

```bash
# Frontend
cd frontend/web && pnpm dev

# API Gateway
cd services/api-gateway && pnpm run start:dev

# Spring Boot microservice
cd services/<service-name> && ./mvnw spring-boot:run

# Python microservice (FastAPI)
cd services/<service-name> && uv run uvicorn src.main:app --reload --port <port>
```
