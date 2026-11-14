---
title: "Testing strategy"
status: draft
created: 2026-11-13
updated: 2026-11-14
author: "Owner"
---

# Testing strategy

What is tested where, what runs in CI versus on a developer machine, and where the evidence goes. Commands to run a single suite are in the skill [`testing`](../../.claude/skills/testing/SKILL.md); per-stack conventions (naming, fakes, markers) are in `.claude/rules/core-api.md`, `ai-service.md` and `frontend.md`. This page does not repeat them. The order in which checks gate a change is in [quality gates](quality-gates.md).

## Test layers

| Scope | Layer | Where | Needs Docker | Notes |
|---|---|---|---|---|
| core-api | Unit tests | `services/core-api/src/test/java/**/*Test.java` | no | `./scripts/run-tests.ps1 -Scope core-api -Type unit` (Maven `test`) |
| core-api | `ArchitectureTest` | `services/core-api/src/test/java/com/sopilot/core/ArchitectureTest.java` | no | Part of the unit run. Enforces the layering, tenant-access and hygiene rules behind CLAUDE.md constraints 4 and 7 |
| core-api | Integration tests (`*IT`) | `services/core-api/src/test/java/**/*IT.java` | yes | Testcontainers, real Postgres with the real Flyway chains (`V2Postgres`). Run by `-Type all` (Maven `verify`) |
| ai-service | Unit | `services/ai-service/tests/unit/` | no | No model download, no network; fakes in `tests/fakes.py`. Includes `test_architecture.py` |
| ai-service | Integration | `services/ai-service/tests/integration/` | yes | Auto-marked `integration`; starts a disposable pgvector Postgres with the real `rag` migrations |
| ai-service | `pdf` marker | tests marked `pdf` | no | Need the optional Docling extra and model artifacts; skipped without it |
| ai-service | `tokenizer` marker | tests marked `tokenizer` | no | Need `transformers` and a cached embedding tokenizer; skipped without them |
| Database | Tenant isolation (FR-19) | `tests/tenant-isolation/` | yes | Every tenant table of `core` and `rag`, both application roles; see its [README](../../tests/tenant-isolation/README.md) |
| Database | Negative control | same suite with `ISOLATION_MUTATION=disable-rls` | yes | Must **fail**. A pass means the suite looks at nothing |
| Retrieval | Eval harness | `eval/tests/` (separate uv project) | no | Imports `sopilot_ai.retrieval`, so harness and service rank identically. See [`eval/README.md`](../../eval/README.md) before quoting any number |
| Frontend | Build and lint | `./scripts/validate-build.ps1 -Scope web` | no | `pnpm build` + `pnpm lint`. `frontend/web/package.json` has no `test` script, so `run-tests.ps1 -Scope frontend` errors by design |
| Frontend | Browser checks | manual, in a browser | no (needs the stack running) | See below |

### Browser and end-to-end checks

A green build is not visual verification. For a UI change, open the page in a browser, walk each acceptance criterion and record which browsers and viewports were **not** checked.

Playwright is **not installed** in this repository: `frontend/web/package.json` has no `@playwright/test`, and `tests/e2e/` is empty. Adding it is a new dependency that needs the owner's agreement first (CLAUDE.md constraint 12). Until then, browser evidence is a manual check written up in a test report. The frontend is still wired to V1 until ticket V2-15, so most V2 flows are exercised through the HTTP APIs, not the UI.

### Legacy test material

`tests/integration/google-auth-flow.mjs`, `tests/smoke/`, `scripts/test-google-auth.ps1` and the Google-auth and Playwright sections of `tests/README.md` belong to the V1 stack and are not part of the V2 gates.

## What runs where

| Check | CI | Locally |
|---|---|---|
| core-api unit + `ArchitectureTest` | `ci.yml` job `core-api-unit` (`./mvnw -B test`) | `run-tests.ps1 -Scope core-api -Type unit` |
| core-api `*IT` (all) | **not run in full**; only the isolation ITs below | `run-tests.ps1 -Scope core-api -Type all` |
| ai-service ruff + unit | `ci.yml` job `ai-service-unit` (`uv sync --extra dev`, `ruff check`, `pytest tests/unit`) | `run-tests.ps1 -Scope ai-service -Type unit` (installs `--extra pdf`, so `pdf` tests run) |
| ai-service integration (all) | **not run in full**; only the isolation files below | `run-tests.ps1 -Scope ai-service -Type integration` |
| Migrations (naming, gaps, immutability, destructive DDL) | `ci.yml` job `migrations` | `./scripts/check-migrations.ps1` |
| Secret scan | `ci.yml` job `secret-scan` (gitleaks) | none |
| DB tenant isolation + negative control | `tenant-isolation.yml` jobs `database`, `negative-control` | `cd tests/tenant-isolation; uv run pytest -v` |
| core-api isolation ITs | `tenant-isolation.yml` job `core-api` (`TenantIsolationIT`, `TenantIsolationApiIT`) | `-Dit.test=...` (see the skill) |
| ai-service retrieval / QA / feedback isolation | `tenant-isolation.yml` job `ai-service` (`test_retrieval.py`, `test_qa_isolation.py`, `test_feedback_isolation.py` and three named `test_qa_api.py` cases) | `pytest` on the same files |
| Department authorization (FR-29) | `tenant-isolation.yml` job `department-authorization` (`DepartmentAuthorizationIT`, `test_department_authorization.py`) | same commands |
| Eval harness | not in CI | `cd eval; uv sync --extra dev; uv run pytest -q` |
| Frontend build | `ci.yml` job `frontend-and-gateway` (`pnpm build`, no lint, no tests) | `validate-build.ps1 -Scope web` |
| Docs check | `ci.yml` job `docs` (`pwsh ./scripts/docs/check-docs.ps1`, then `eval/sopilot_eval/plan_check.py`; first passed on GitHub on PR #14) | `./scripts/docs/check-docs.ps1` |

Consequences to keep in mind when reporting results:

- The rest of the Docker-backed core-api ITs and ai-service integration tests (everything outside the isolation selections above) have **no CI job**. They count as verified only when someone ran them locally and recorded the result.
- CI runs ai-service with `--extra dev` only, so `pdf`-marked tests skip there. Say which environment you ran.
- Frozen V1 jobs (`backend-java`, `backend-python`, and the gateway half of `frontend-and-gateway`) stay green until ticket V2-17 deletes V1; they are not V2 evidence.
- Without Docker, core-api `*IT` fail at container start, while ai-service integration tests and `tests/tenant-isolation` **skip** (`pytest.skip("Docker is not available")`) and the run still exits 0. Check the skipped count. Report "not run: Docker unavailable", never "passed".

## Where evidence goes

| Evidence | Location |
|---|---|
| Acceptance of a ticket | The ticket's "Evidence" section: each command with its result line. `done` also needs owner review (see [quality gates](quality-gates.md)) |
| Risky or cross-service verification, plan | `docs/quality/test-plans/` (template [`test-plan.md`](../templates/test-plan.md), id `TEST-PLAN-NNN`). The folder is created with the first plan |
| Verification result | [`docs/quality/test-reports/`](test-reports/) (template [`test-report.md`](../templates/test-report.md), id `TEST-REPORT-NNN`) |
| Screenshots, traces, logs, binaries | `artifacts/testing/<run-id>/`, gitignored (`/artifacts/` in `.gitignore`). The report links the folder; a reviewer cloning the repository will not have it |
| Retrieval metrics | `eval/results/` (gitignored); figures are reported through a research document, not copied from run folders |

A report lists what was actually run, the results, and what was not verified. Never claim a suite passed that was not run in that piece of work. Workflow and ids: skill [`project-docs`](../../.claude/skills/project-docs/SKILL.md).
