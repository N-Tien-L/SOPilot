---
title: "Troubleshoot the local stack"
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
---

# Troubleshoot the local stack

**When:** a service will not start, a request returns an unexpected status, or a document does not become `READY`. **Risk:** read-only checks only. Do not reset volumes, edit applied migrations, or disable RLS or auth to test a theory. Finding the root cause of a code bug (hypothesis, evidence, fix) is the skill [`debug-and-diagnose`](../../.claude/skills/debug-and-diagnose/SKILL.md); this page lists the operational first checks. Normal startup: [local development](local-development.md).

## Steps

Start with the state of the stack and the recent history:

```powershell
docker compose -f docker-compose.v2.yml ps -a
git log --oneline -15
```

Then find the symptom:

| Symptom | First checks | Usual fix |
|---|---|---|
| `docker compose up` stops with `set <NAME> in .env` | A required variable is missing from the root `.env` | Add it (names in the root `.env.example`, values from the owner). `./scripts/check-env.ps1` reports missing keys without printing values |
| Postgres or MinIO container not healthy | `docker compose -f docker-compose.v2.yml logs --tail 50 postgres` (or `minio`); port `55432`/`59000`/`59001` already in use | Free the port or change `V2_POSTGRES_PORT` / `V2_MINIO_*_PORT` |
| `flyway-core` / `flyway-rag` exit non-zero | `docker compose -f docker-compose.v2.yml logs flyway-core` | A checksum mismatch means an applied migration was edited: restore the file from git. Never repair on the persistent volume without the owner. Run `./scripts/check-migrations.ps1` |
| core-api starts but `GET /actuator/health` is `503`, or the log repeats `CannotGetJdbcConnectionException` | The database is unreachable or `SOPILOT_DB_*` is wrong. core-api does **not** exit for this: run from source with no database settings it started in about 3 s, health was `503` and the outbox dispatcher logged the connection failure (observed 2026-11-13). Missing S3 settings do not stop startup either; document calls fail with `503` | Start Postgres (`127.0.0.1:55432`) and load the core-api environment into the shell |
| core-api exits at startup | Outside the `local`/`test` profiles it needs `SOPILOT_JWT_PRIVATE_KEY_PATH` and `SOPILOT_NONCE_HMAC_KEY`; `SOPILOT_ACCESS_TTL` above `PT15M` also fails startup | Use the `local` profile, or provide both keys |
| ai-service exits at startup | `SOPILOT_DB_URL` or `SOPILOT_INTERNAL_TOKEN` unset (both are required) | Load the ai-service environment; the DB URL uses the `postgresql://` form, not JDBC |
| `401` on `/api/v1/**` or `/ai/v1/**` | Bearer present? Token older than 15 minutes? After a core-api restart in `local` all tokens are invalid | Sign in again (dev login). ai-service verifies tokens through `SOPILOT_CORE_JWKS_URL` (`http://localhost:8080/.well-known/jwks.json` from source) |
| `404` for something visible in the database | Expected when it belongs to another workspace: compare the token's workspace with the row's `workspace_id` | none |
| Document stuck in `UPLOADED` / `PROCESSING` | Is the worker running? `SOPILOT_INTERNAL_TOKEN` equal in core-api and ai-service? Rows in `core.outbox_events` (`status`, `attempts`, `last_error`; `DEAD` = gave up) and `rag.ingestion_jobs` | Start the worker; align the token. A callback with a stale `attempt` is ignored by design |
| ai-service cannot read objects | `SOPILOT_S3_REGION` set (default `us-east-1`)? Bucket name and S3 AI keys equal to the root file? The ai-service endpoint has **no** scheme (`localhost:59000`); core-api's has one | Fix the value and restart |
| First ingest or question hangs | Embedding model download from Hugging Face on first use; Modal cold start is about 160 s with the cache on the volume and about 320 s the first time, per `infrastructure/modal/README.md` (figures recorded there, not measured here), longer than the 120 s client timeout in `providers/llm.py` | Wait, or warm the endpoint (`infrastructure/modal/README.md`) |
| Question fails with `LLM_UNAVAILABLE` or `503` | `SOPILOT_LLM_BASE_URL` (ends in `/v1`), `SOPILOT_LLM_API_KEY` and `SOPILOT_LLM_MODEL` match the Modal deployment; the endpoint is warm | Correct the variables; retry after warm-up |
| Retrieval returns nothing | `/health` `degraded` with `staleVersions`: run [reindex](reindex.md). Otherwise the `document_access` row must exist with an active version and the right visibility or department | Reindex, or re-check access sync |
| `permission denied` for a table or function | A grant or policy is missing in a migration (role table in `infrastructure/db/README.md`) | Fix with a new migration, skill `flyway-migration` |
| Metadata suggestions are rules only | `SOPILOT_GROQ_API_KEY` unset: the worker logs `suggest_key_missing` but still builds the chain; the Groq call then fails (`LLMError`) and the runner returns `RULES_FALLBACK` (`suggest/runner.py`). A chain that cannot be built gives the same result | Optional; set it only if LLM suggestions are wanted |

## Verify

Read-only SQL, no writes and no DDL:

```powershell
docker exec sopilot-v2-postgres psql -U postgres -d sopilot -c "SELECT 1"
```

Replace the statement with a `SELECT` on the table you are inspecting. Re-run the failing request after the fix and confirm the status and the `traceId` of the error envelope are gone.

## Roll back

These checks change nothing. If a fix made things worse, stop the service, restore the previous configuration, and start again as in [local development](local-development.md). Anything that needs a volume reset, a migration repair or a secret value goes to the owner.
