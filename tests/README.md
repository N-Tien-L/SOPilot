# SOPilot Platform Test Suite

## Google identity/admission integration

Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-google-auth.ps1` from the repo root. It runs auth/user unit tests and then real HTTP against two service processes, fresh PostgreSQL, and local RSA-signed provider tokens/JWKS. Docker must have `pgvector/pgvector:pg16` cached; Java, Node and Maven dependencies must already be installed. The runner is offline and installs nothing. Supply `-MavenPath` if Maven cannot be discovered.

Only the new labelled test container is removed. Existing containers/volumes are untouched. Logs and generated test configuration live in ignored `scratch/google-auth-*`; they contain ephemeral test credentials, never copy them into source control. This suite checks backend auth, concurrent enrollment, token validation and session lifecycle. Hosted Google UI, roster Excel import UI, chatbot navigation and audit RabbitMQ delivery still belong to M1-06.

Checkpoint 2026-10-15: frontend has no `test` script yet; build/typecheck/lint are separate checks. Ingestion currently keeps mixed mock-based tests in `tests/ingestion_tests`, so use `-Scope ingestion-service -Type all`; there are no separate unit/integration folders. Java `all` runs Maven verify; a separate integration profile is not configured. Missing suites must be reported as unavailable, never as PASS. See [handoff](../docs/04-reports/HANDOFF-implementation-2026-10-15.md).

This directory contains **platform-wide, cross-service, and end-to-end (E2E) automated tests**, along with shared test fixtures and performance test configurations.

---

## 🏗 Test Architecture & Placement

SOPilot follows a microservices monorepo structure. Testing is distributed as follows:

| Test Scope | Target Location | Technology / Tooling |
|---|---|---|
| **Platform E2E** | `tests/e2e/` | Playwright, TypeScript |
| **Cross-Service Integration** | `tests/integration/` | Pytest / Jest / Newman / HTTP test clients |
| **Tenant isolation (V2, FR-19)** | `tests/tenant-isolation/` | Pytest + psycopg against the real V2 migrations and roles; see its README |
| **Smoke / Health Checks** | `tests/smoke/` | PowerShell / Bash / Python scripts |
| **Performance & Load** | `tests/performance/` | k6 / Locust |
| **Shared Test Fixtures** | `tests/fixtures/` | Sample documents, mock JSON payloads, seed SQLs |
| **Service Unit & Integration** | `services/<service-name>/tests` or `src/test` | JUnit 5 (Java), Pytest (Python), Jest (Gateway) |
| **Ad-hoc Utility Scripts** | `scripts/testing/` | Custom developer tools & local test helpers |

---

## 📁 Directory Structure

```text
tests/
├── e2e/                     # End-to-end UI & browser-driven test suites (e.g., Playwright specs)
├── integration/             # Multi-service API flows & asynchronous RabbitMQ pipeline tests
├── smoke/                   # Lightweight health checks & smoke tests for deployed environments
├── performance/             # Load, stress, and benchmark test scenarios
└── fixtures/                # Shared mock inputs & test datasets
    ├── documents/           # Sample test files (PDF, DOCX, TXT) for ingestion/dedup testing
    ├── payloads/            # JSON payloads for API requests/mock responses
    └── seeds/               # Deterministic SQL seed files for test environments
```

---

## 🏷 Naming & File Conventions

- **Playwright / TypeScript E2E**: `*.spec.ts` (e.g., `violation-management.spec.ts`, `document-upload.spec.ts`)
- **Python Integration**: `test_<feature>_<scenario>.py` (e.g., `test_ingestion_pipeline.py`)
- **Smoke Tests**: `smoke_<service_or_feature>.[ps1|py|sh]`
- **Fixtures**: Descriptive lower-kebab-case filenames (e.g., `sample-policy-draft.pdf`, `user-registration.payload.json`)

> [!NOTE]
> All subfolders contain a `.gitkeep` file so that empty directories remain tracked in Git until test files are populated.

---

## 🚀 Execution & Quick Commands

### Pre-commit Verification
Run the unified pre-commit validation script from the project root:
```powershell
./scripts/pre-commit-check.ps1
```

### Platform Smoke Check
Check health and connectivity of all active services and infrastructure:
```powershell
./tests/smoke/smoke-check.ps1
```

### Running Individual Service Tests
Run tests by service scope using the centralized test runner:
```powershell
./scripts/run-tests.ps1 -Scope <service-name> -Type <all|unit|integration>
```
Valid scopes: `auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`, `ai-qa-service`, `ingestion-service`, `api-gateway`, `frontend`.
