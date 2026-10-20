# SOPilot Developer & AI Agent Handbook (`AGENTS.md`)

> **Notice:** This project was originally codenamed *Poliwise* and has been unified under the product name **SOPilot**. The legacy name still appears in Java packages (`com.poliwise.*`), some RabbitMQ exchanges and some config defaults; do not rename these in unrelated tasks.
> PostgreSQL database is named `sopilot` (user: `sopilot`). The application schemas are strictly partitioned by domain: `core`, `metadata`, `knowledge`, `conversation`, `analytics` (created in `infrastructure/init-db/000_bootstrap.sql`).

This file is the single entry point for agents (Claude Code reads it via `CLAUDE.md`; `GEMINI.md` points here).

> **V2 transition (temporary, remove in `V2-17`):** V2 is being written as two new services, `services/core-api` (Spring Boot) and `services/ai-service` (FastAPI), with their own `docker-compose.v2.yml` and Flyway migrations in `infrastructure/db/migrations/` ([ADR-004](docs/02-architecture/adr/ADR-004-two-service-architecture.md) §4.4–4.5). The eight services, gateway, `docker-compose.yml` and `infrastructure/init-db/` described below are **frozen V1**: read and port from them, do not extend them. `frontend/web` is changed in place by `V2-15`. Run one stack at a time. For V2 work, the V2 tickets and `TECH-V2-*` designs win over the topology and `.agent/context/` below until `V2-17` rewrites them.

---

## 🧭 System Topology & Architecture

| Service | Port | Tech Stack | Database Schema / Store | Primary Responsibility |
|---|---|---|---|---|
| **Frontend** | `3000` (published) | Next.js 16, React 19, TypeScript, Tailwind 4, Zustand | Browser / Local Storage | Employee Q&A, Admin Document & User Management UI |
| **API Gateway** | `3001` (published) | NestJS 11, TypeScript | In-memory / Reverse Proxy | Single client entry point, JWT verification, RBAC guards, trace ID |
| **auth-service** | `8081` | Spring Boot 3.3.4, Java 17 | `core` | Authentication, token issuance/revocation, Google identity + roster admission |
| **user-service** | `8082` | Spring Boot 3.4.3, Java 17 | `core` | User profiles, departments, pre-provisioned employee roster |
| **knowledge-service** | `8083` | Spring Boot 3.4.3, Java 17 | `knowledge` + MinIO | Document lifecycle, versioning, upload/delete events |
| **metadata-service** | `8084` | Spring Boot 3.4.3, Java 17 | `metadata` | Document tags, categories, department visibility rules |
| **feedback-service** | `8085` | Spring Boot 3.4.3, Java 17 | `analytics` | Feedback votes, analytics metrics, unanswered questions |
| **ai-qa-service** | `8086` | FastAPI, Python >=3.11 | `conversation` | Hybrid RAG (pgvector dense + BM25 sparse, RRF), streaming synthesis |
| **ingestion-service** | `8088` | FastAPI, Python >=3.11 | Stateless (RabbitMQ + MinIO) | Text extraction (PDF/DOCX), chunking, embedding |
| **PostgreSQL** | `5432` | Postgres 16 + pgvector | Database `sopilot` | Primary structured and vector storage |
| **RabbitMQ** | `5672` / `15672` | AMQP 0-9-1 | Exchanges: `sopilot.events`; legacy `poliwise.auth.exchange`, `poliwise.user.exchange` (auth/user `RabbitMQConfig.java`) | Asynchronous inter-service events and ingestion |
| **MinIO** | `9000` / `9001` | S3 API compatible | Compose bucket: `sopilot-documents` (`MINIO_BUCKET_NAME`); code defaults still `poliwise-documents` | Binary document storage |
| **Redis** | `6379` | Redis 7 (password required) | Cache | Used by `api-gateway` and `ai-qa-service` via `REDIS_URL` |

In `docker-compose.yml` only the frontend (`3000`) and gateway (`3001`) publish ports to the host. Every other service and all infrastructure are reachable only on the `sopilot-network` bridge network, by container name.

Detailed ownership: [.agent/context/service-boundaries/responsibilities.md](.agent/context/service-boundaries/responsibilities.md) and [ownership-matrix.md](.agent/context/service-boundaries/ownership-matrix.md). When docs and code disagree, code wins; see "Known doc/code drift" in [CLAUDE.md](CLAUDE.md).

---

## 🛡️ Critical Safety Guardrails (MANDATORY)

1. **Volume & Database Protection**:
   - Schema modifications must be written as numbered additive scripts in `infrastructure/init-db/` (next number after the highest existing one), with `infrastructure/init-db/README.md` and `.agent/context/database/` updated. Init scripts only run on a fresh volume; existing databases need the script applied explicitly.
   - Services must not write tables outside the schema(s) they own, and cross-schema SQL joins are prohibited; use HTTP calls or events.
   - `./infrastructure/init-db/reset-and-bootstrap.ps1` deletes the Postgres Docker volume; run it only when the user explicitly asks for a local reset. Never `docker compose down -v` or prune volumes.
   - **NEVER** execute destructive DDL (`DROP DATABASE`, `DROP SCHEMA`, `TRUNCATE TABLE`) on a live database.
2. **File System Scoping**:
   - All operations must strictly remain inside this repository. Never modify or delete files outside the repository root.
   - **NEVER** run recursive wildcard deletions (`rm -rf *`, `Remove-Item * -Recurse`). Specify exact file targets.
3. **Secrets & Environment Isolation**:
   - **NEVER** read, print, log or commit `.env` contents or hardcode secrets/API keys (`GROQ_API_KEY`, `EMBEDDING_API_KEY`, DB passwords, JWT secrets).
   - Use `.env.example` with dummy values for documentation.
4. **Git Discipline**:
   - Inspect `git status` first; never discard, stash, reset or overwrite someone else's staged/unstaged/untracked changes.
   - **NEVER** commit directly to `main`. Develop on `develop` or short-lived feature branches (`feat/*`, `fix/*`).
   - Follow Conventional Commits: `<type>(<scope>): <summary>`.
5. **Code Hygiene** (enforced by `pre-commit-check.ps1`): no new `console.log` / `System.out.println` / `print(`; every `TODO`/`FIXME` carries a ticket reference.

---

## 📐 Spec-Driven Workflow

Specs live in `docs/` (written in Vietnamese); long-lived technical context lives in `.agent/context/`. The frontmatter schema, status vocabulary and the meaning of `done` are defined once in [docs/README.md](docs/README.md); follow it, do not redefine it.

1. **Spec chain**: PRD (`docs/01-requirements`) → ADR / TECH (`docs/02-architecture`) → PLAN + tickets (`docs/03-plans`) → code → AUDIT (`docs/04-reports`). Do not start a PLAN without an approved PRD.
2. **Progress source**: `docs/03-plans/` is the only progress source (the old `docs/plans/` copy was removed in V2-04).
3. **Implementing a ticket** (skill `execute-ticket`), in this order:
   1. Service: entities, repositories, services, versioned REST controllers; additive migration in `infrastructure/init-db/` if the schema changes; RabbitMQ events if other services must react.
   2. Gateway: proxy routes and RBAC guards in `services/api-gateway`.
   3. Frontend: types in `frontend/web/types`, API client `frontend/web/lib/api.ts`, components (`.agent/rules/frontend.md`).
   4. Verify: targeted tests, `validate-build.ps1` per touched scope, `pre-commit-check.ps1`.
   5. Docs: update `.agent/context/` for any endpoint, schema, event or RBAC change, and the ticket/PLAN status.
4. **Status**: a ticket moves to `done` only with acceptance evidence (tests, commands, SQL/event checks) after review. Keep PLAN counters in sync with ticket frontmatter.

---

## 📜 Working Rules for AI Agents

1. **Check Boundaries First**: Consult `.agent/context/` (index: [.agent/context/README.md](.agent/context/README.md)) before changing data models, inter-service contracts, or routing.
2. **Progressive Skill Loading**: load only the skill that matches the work.
   - Requirements analysis & PRD: `.agent/skills/analyze-requirements/SKILL.md`
   - Architecture, technical design & ADR: `.agent/skills/design-architecture/SKILL.md`
   - Planning & decomposition: `.agent/skills/plan-and-decompose/SKILL.md`
   - Ticket implementation: `.agent/skills/execute-ticket/SKILL.md`
   - Writing tests (unit/integration/E2E): `.agent/skills/write-test/SKILL.md`
   - Running tests & verification: `.agent/skills/run-test/SKILL.md`
   - Quality, coverage & audit reports: `.agent/skills/analyze-quality/SKILL.md`
   - Code review: `.agent/skills/code-review/SKILL.md`
   - Debugging & root-cause analysis: `.agent/skills/debug-and-diagnose/SKILL.md`
   - Branching, commits, PRs & releases: `.agent/skills/repo-contributing/SKILL.md`
   - Spring Boot backend: `.agent/skills/springboot-backend/SKILL.md`
   - Python FastAPI: `.agent/skills/python-backend/SKILL.md`
   - NestJS API Gateway: `.agent/skills/nestjs-gateway/SKILL.md`
   - Next.js web frontend: `.agent/skills/nextjs-frontend/SKILL.md`
3. **Living Documentation**: If you alter endpoints, schemas, events or RBAC rules, update the corresponding file in `.agent/context/` in the same change and say which docs you updated.
4. **Verify, don't assume**: never treat scaffold or placeholder code as wired; verify the real call path on disk.

---

## 🛠️ Central Scripts & Common Commands

Run all scripts from the repository root (PowerShell):

```powershell
./scripts/pre-commit-check.ps1                                   # diff checks (debug/secrets/TODO/.env) + tests for affected services
./scripts/run-tests.ps1 -Scope <test-scope> -Type <all|unit>      # see scope table below
./scripts/validate-build.ps1 -Scope <build-scope>                 # build + lint for one scope
./scripts/check-conventions.ps1 -Scope <build-scope>              # branch name, file scope, debug statements
./scripts/check-services.ps1                                      # health of running services and infra ports
./scripts/trace-request.ps1 -Endpoint "/api/v1/users/profile"     # trace gateway routing
```

| Target | `run-tests.ps1 -Scope` | `validate-build.ps1` / `check-conventions.ps1 -Scope` | Notes |
|---|---|---|---|
| Spring services | `auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service` | `auth`, `user`, `knowledge`, `metadata`, `feedback` | `-Type all` = `mvnw verify`, `unit` = `mvnw test`; `integration` is not supported |
| ai-qa-service | `ai-qa-service` | `ai-qa` | `tests/unit`, `tests/integration` |
| ingestion-service | `ingestion-service` | `ingestion` | Only `-Type all` (tests live in `tests/ingestion_tests`) |
| API Gateway | `api-gateway` | `gateway` | `-Type all|unit` (Jest); no e2e config |
| Frontend | not supported (no `test` script) | `web` | Gates are `pnpm build` + `pnpm lint` |

- `validate-build.ps1`: Spring = `mvnw compile`; Python = `compileall` + `ruff check`; gateway = `pnpm build` + eslint; web = `pnpm build` + `pnpm lint`.
- `check-conventions.ps1` also enforces the branch pattern `{type}/{scope}-{name}` and flags files outside the scope's directory; on multi-area branches expect violations and judge them, do not "fix" them by moving files.
- Do not start the full stack or run every suite unless the task needs it; scope checks to what changed.

### Direct Service Commands

```bash
cd frontend/web && pnpm dev                                          # :3000
cd services/api-gateway && pnpm run start:dev                        # set PORT=3001; code falls back to 3000
cd services/<spring-service> && ./mvnw spring-boot:run               # mvnw.cmd on Windows
cd services/<spring-service> && ./mvnw -Dtest=ClassName#method test  # single test
cd services/ai-qa-service && uv run uvicorn src.main:app --reload --port 8086
cd services/ingestion-service && uv run uvicorn src.main:app --reload --port 8088
```
