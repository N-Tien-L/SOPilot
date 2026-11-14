# tests/

Cross-service tests that do not belong to a single service. What is tested where, and what CI runs, is in
[`docs/quality/testing-strategy.md`](../docs/quality/testing-strategy.md); the commands per suite are in the
[`testing`](../.claude/skills/testing/SKILL.md) skill. Service tests live with their service
(`services/core-api/src/test`, `services/ai-service/tests`).

## What is here

| Path | Status | What it is |
|---|---|---|
| `tenant-isolation/` | V2, run in CI | Database-level proof that no workspace reads or changes another's data (FR-19). See its [README](tenant-isolation/README.md) |
| `smoke/smoke-check.ps1` | V1, frozen | Wraps `scripts/check-services.ps1`, which probes the eight V1 services. It does not know the V2 stack |
| `integration/google-auth-flow.mjs` | V1, frozen | Driven by `scripts/test-google-auth.ps1` against two V1 processes. Not part of V2 |
| `e2e/`, `performance/`, `fixtures/` | Empty | Only `.gitkeep` files. No V2 browser, load or shared-fixture suite exists yet |

The two V1 entries go away with ticket V2-17 (`.claude/rules/v1-frozen.md`); do not extend them.

## Running

```powershell
./scripts/run-tests.ps1 -Scope core-api -Type unit          # no Docker
./scripts/run-tests.ps1 -Scope ai-service -Type unit
cd tests/tenant-isolation; uv run pytest -v                  # needs Docker
./scripts/pre-commit-check.ps1                               # before proposing a commit
```

A suite that does not exist is reported as unavailable, never as a pass.
