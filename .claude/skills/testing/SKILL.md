---
name: testing
description: Write, run and triage SOPilot V2 tests (core-api JUnit/Testcontainers, ai-service pytest, tests/tenant-isolation, eval). Use when adding tests for a change, choosing the narrowest suite to run, or when a test fails and you need the cause. For live-service bugs without a failing test, use debug-and-diagnose.
---

# V2 testing

Per-stack conventions (naming, fakes, markers) are in `.claude/rules/core-api.md` and `.claude/rules/ai-service.md`. Do not restate or change them here.

## Choose what to run (narrowest first)

| Need | Command | Docker |
|---|---|---|
| One Java unit test | `cd services/core-api; ./mvnw test -Dtest=Class#method` | no |
| core-api unit + ArchitectureTest | `./scripts/run-tests.ps1 -Scope core-api -Type unit` | no |
| One Java IT | `cd services/core-api; ./mvnw verify -Dit.test=NameIT -Dtest=NoSuchTest -Dsurefire.failIfNoSpecifiedTests=false` | yes |
| core-api everything | `./scripts/run-tests.ps1 -Scope core-api -Type all` | yes |
| One pytest | `cd services/ai-service; uv run --extra dev pytest tests/unit/test_x.py::test_name -q` | no |
| ai-service unit / integration | `./scripts/run-tests.ps1 -Scope ai-service -Type unit` / `-Type integration` | no / yes |
| DB tenant isolation (FR-19) | `cd tests/tenant-isolation; uv run pytest -v` | yes |
| Retrieval harness | `cd eval; uv run pytest -q` | no |

If Docker is not running, integration suites fail at container start. Report "not run: Docker unavailable"; never report them as passed.

## Write a test

1. Name the behaviour, not the method: Java `twoConcurrentRetriesCreateOneJob`, Python `test_a_malformed_workspace_id_is_an_error_never_rows`.
2. Prefer real collaborators: real Postgres via `ApiIT`/`V2Postgres` or the ai-service integration conftest; in-process fakes (`InMemoryStorage`, `RecordingAiClient`, `tests/fakes.py`) at the network boundary. Mock only at a boundary that has no fake.
3. A bug fix starts with a test that fails for the reported reason. Run it red, then fix.
4. Tenant-scoped behaviour: assert that another workspace sees `404`/nothing, not just that the owner sees data.
5. Keep unit tests free of Docker, network and model downloads. They run in CI on every push.

## Triage a failure

1. Read the first failure, not the last: the exact assertion, exception type, file and line.
2. Classify it:
   - Assertion mismatch: the code or the expectation is wrong. Check the ticket/TECH to see which.
   - Testcontainers/`Connection refused`: environment (Docker), not code.
   - `permission denied for table|function` as `sopilot_*_app`: a missing grant/policy in a migration.
   - Rows missing only under the app role: RLS context not bound (`TenantTx`/`tenant_tx` missing) or the wrong workspace.
   - Flaky under concurrency: look for ordering assumptions (for example RRF tie order, fixed in `262d7fc`).
3. Reproduce with the single-test command. Confirm the cause with evidence (a log line, a query, a minimal change) before editing.
4. Fix the cause in the smallest place. Do not change unrelated tests, loosen assertions or add `@Disabled`/`skip` to get green. If the expectation itself is outdated, say so and cite the spec.
5. Re-run the single test, then the suite for the touched scope.

## Done when

The new or changed behaviour has a test that failed before the change (or would have). The narrowest relevant suites ran, with results quoted. Skipped or unrun suites are named with the reason.
