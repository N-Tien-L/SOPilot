# General Agent Rules

> **Notice:** This project was originally codenamed *Poliwise* and has been unified under the product name **SOPilot**.
> PostgreSQL database `sopilot` uses the domain schemas `core`, `metadata`, `knowledge`, `conversation`, `analytics` (created in `infrastructure/init-db/000_bootstrap.sql`). There is no `poliwise_*` schema prefix. **DO NOT rename database schemas or prefix tables.**

Mandatory working rules and common operations for AI coding agents in the SOPilot repository.

---

## 1. Mandatory Working Rules

- **Check Boundaries First**: Always check architecture and boundary context before implementing features, changing database interactions, or touching service contracts.
- **Sources of Truth for Architecture & Ownership**:
  - `.agent/context/overview.md` (System overview & service topology)
  - `.agent/context/architecture/` (Technical architecture & frontend design)
  - `.agent/context/service-boundaries/` (Responsibilities, API contracts, RabbitMQ events)
  - `.agent/context/database/` (Schemas, table definitions, ERD)
  - `.agent/context/authorization/` (RBAC matrix & dual-strategy security)
  - `.agent/context/storage/` (Document lifecycle & MinIO object storage)
  - `.agent/context/patterns/` (Polyglot architectural design patterns)
- **Living Documentation Rule**:
  - If you add or modify REST endpoints, DB schema, RBAC roles, or service responsibilities, update related files in `.agent/context/`.
  - Briefly summarize which documentation files were updated in your response.
  - Proactively propose updates if context docs are outdated or missing.
- **Verification Over Assumption**: Verify real implementation code before extending features. Some parts of the codebase may still be scaffold or placeholder code.
- **Ignore Build Artifacts**: Ignore build and generated artifacts such as `target/`, `node_modules/`, `.pytest_cache/`, `dist/`, and `build/`.
- **Preserve Documentation Integrity**: Preserve all existing comments and docstrings that are unrelated to your code changes, unless explicitly instructed otherwise.

---

## 2. Recommended Implementation Flow

When adding or extending a feature end-to-end:

1. **Service API / Domain Logic**: Implement or update entities, repositories, and domain logic in the target microservice first.
2. **API Gateway**: Update routes, proxies, guards, and contracts in `services/api-gateway`.
3. **Frontend**: Update frontend types/interfaces, API client methods (`frontend/web/lib/api.ts`), and React components.
4. **Verification**: Run lint, type-checks, and automated tests (`./scripts/pre-commit-check.ps1` or `./scripts/run-tests.ps1`).
5. **Documentation**: Update relevant `.agent/context/` and `.agent/context/` documentation files.

---

## 3. Common Commands

### Frontend (`frontend/web`)
```bash
cd frontend/web
pnpm install       # Install dependencies
pnpm dev           # Start development server (port 3000)
pnpm build         # Build production bundle
pnpm start         # Start production server
pnpm lint          # Run ESLint
# No `test` script exists yet; build + lint are the frontend gates
```

### API Gateway (`services/api-gateway`)
```bash
cd services/api-gateway
pnpm install       # Install dependencies
pnpm run start:dev # Start development server with watch mode (port 3001)
pnpm run start     # Start server
pnpm run build     # Build production bundle
pnpm run lint      # Run ESLint
pnpm test          # Run unit tests
# `test:e2e` is declared but test/jest-e2e.json does not exist yet
```

### Spring Boot Services (`services/<service-name>`)
```bash
cd services/<service-name>
./mvnw spring-boot:run                   # Run locally
./mvnw package                           # Build JAR artifact
./mvnw test                              # Run all tests
./mvnw -Dtest=ClassName test             # Run single test class
./mvnw -Dtest=ClassName#methodName test  # Run single test method
```

### AI Q&A Service (`services/ai-qa-service`)
```bash
cd services/ai-qa-service
uv sync                                              # Install / sync dependencies
uv run uvicorn src.main:app --reload --port 8086     # Run service
uv run pytest                                        # Run pytest suite
```

### Ingestion Service (`services/ingestion-service`)
```bash
cd services/ingestion-service
uv sync                                              # Install / sync dependencies
uv run uvicorn src.main:app --reload --port 8088     # Run service
uv run pytest                                        # Run pytest suite
```

### Full Stack (Docker)
```bash
docker compose up        # Start all platform services in containers
docker compose down      # Stop all services
```

### Automated Platform & Pre-Commit Verification
```powershell
./scripts/pre-commit-check.ps1   # Full automated pre-commit checklist
./scripts/run-tests.ps1 -Scope <service-name> -Type <all|unit|integration>
```
Valid scopes for `run-tests.ps1`: `auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`, `ai-qa-service`, `ingestion-service`, `api-gateway`, `frontend`.

