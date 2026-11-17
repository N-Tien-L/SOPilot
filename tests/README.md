# tests/

Cross-service tests that do not belong to a single service. What is tested where, and what CI runs, is in
[`docs/quality/testing-strategy.md`](../docs/quality/testing-strategy.md); the commands per suite are in the
[`testing`](../.claude/skills/testing/SKILL.md) skill. Service tests live with their service
(`services/core-api/src/test`, `services/ai-service/tests`).

## What is here

| Path | Status | What it is |
|---|---|---|
| `tenant-isolation/` | V2, run in CI | Database-level proof that no workspace reads or changes another's data (FR-19). See its [README](tenant-isolation/README.md) |
| `smoke/smoke-check.ps1` | V2, local | Wraps `scripts/check-services.ps1`: core-api, ai-service, web, ai-worker (when in compose), Postgres and MinIO, honouring the `V2_*_PORT` variables; exits 1 if any check is red. Not run in CI (needs the running stack) |
| `e2e/`, `performance/`, `fixtures/` | Empty | Only `.gitkeep` files. No V2 browser, load or shared-fixture suite exists yet |

## Running

```powershell
./scripts/run-tests.ps1 -Scope core-api -Type unit          # no Docker
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/run-tests.ps1 -Scope frontend                      # Vitest
cd tests/tenant-isolation; uv run pytest -v                  # needs Docker
./tests/smoke/smoke-check.ps1                                # the running stack
./scripts/pre-commit-check.ps1                               # before proposing a commit
```

A suite that does not exist is reported as unavailable, never as a pass.
