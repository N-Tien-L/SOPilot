---
name: debug-and-diagnose
description: Find the root cause of a SOPilot V2 runtime problem (core-api, ai-service, worker, outbox, Flyway, MinIO, provider calls) before changing code. Use for bug reports, a stuck document status, 401/403/404 surprises, empty retrieval results or a container that will not start. For a failing test with a clear assertion, the testing skill is enough.
---

# Debug and diagnose (V2)

Rule: no fix without a confirmed cause. Write down the hypothesis, the evidence for it, and the evidence against it.

## 1. Reproduce and capture

- Exact request (method, path, which workspace/role), response body and status, and `traceId` from the error envelope (`{"error":{...},"traceId"}`).
- The state of the stack: `docker compose -f docker-compose.v2.yml ps -a` (Postgres 55432, MinIO 59000/59001). The apps run locally (`mvnw spring-boot:run -Dspring-boot.run.profiles=local`, `uv run uvicorn --app-dir src sopilot_ai.api.app:create_app --factory`, `PYTHONPATH=src uv run python -m sopilot_ai.worker`). V2-16 has not added them to compose yet.
- `git log --oneline -15` for recent changes in the touched area.

## 2. Locate by symptom

| Symptom | First checks |
|---|---|
| 401 on `/api/v1/**` | Bearer present? Token expired (≤ 15 min)? Issuer/kid vs `/.well-known/jwks.json`. `401 INVALID_GOOGLE_TOKEN`: logs carry only a reason code |
| 404 for a resource you can see in the DB | Expected when it belongs to another workspace. Compare the token `wid` with the row's `workspace_id` |
| Empty list or "not found" only through the app | RLS: was the call inside `TenantTx`/`tenant_tx`? Query as `postgres` vs `sopilot_core_app` to compare |
| `permission denied` | Missing GRANT/policy in a migration (`check-migrations.ps1`, then the role table in `infrastructure/db/README.md`) |
| Version stuck in `UPLOADED`/`PROCESSING` | `core.outbox_events` (`status`, `attempts`, `next_attempt_at`, `last_error`; `DEAD` = gave up); `rag.ingestion_jobs` (`QUEUED`/`RUNNING`, lease); `rag.outbox_events` for the callback; `/internal` callbacks need matching `SOPILOT_INTERNAL_TOKEN` on both sides; a stale `attempt` returns `{applied:false}` by design |
| ai-service cannot read objects | `SOPILOT_S3_REGION` must be set (the read-only policy denies GetBucketLocation, fix `e96599c`); bucket name same on both services |
| Retrieval returns nothing | `/health` `degraded` + `staleVersions` means an embedding model/revision mismatch; run `python -m sopilot_ai.admin reindex` (with `PYTHONPATH=src`). Also check the `document_access` row exists with `active_version_id` and visibility/department |
| Flyway service exits non-zero | Checksum mismatch means an applied migration was edited. Never "repair" on the persistent volume without the owner |
| Provider 429/5xx | Limits in `config/models.yaml` chain; owner decisions in PLAN-V2 (2026-11-01) |

Inspect data read-only: `docker exec sopilot-v2-postgres psql -U postgres -d sopilot -c "<SELECT ...>"`. No writes, no DDL (the hook blocks DROP/TRUNCATE through psql).

## 3. Confirm, then fix

1. Reduce to the smallest reproduction, ideally a failing test (skill `testing`).
2. Fix the cause where it lives. Do not add retries, broader catches or bigger timeouts to hide it.
3. Verify with the reproduction plus the scope's suite. State what was verified live and what only by tests.

## Report

Symptom → root cause (with file:line and evidence) → fix → verification commands and results → residual risk. If the cause is outside the task (a V1 bug, an infra or provider outage), report it and stop.

## Never

Read `.env` (ask for the value or check `.env.example`), reset volumes, edit applied migrations, or disable RLS/auth to "test a theory" outside a disposable Testcontainers database.
