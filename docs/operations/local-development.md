---
title: "Run the V2 stack locally"
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
---

# Run the V2 stack locally

**When:** starting a work session, or after a reboot. Local only, no deployment (ADR-006). **Risk:** `docker compose down -v`, `docker volume rm|prune` and `docker system prune` delete the Postgres and MinIO volumes, which hold the research corpus and eval state. Never run them; `down` without `-v` is safe (CLAUDE.md constraint 3).

Commands are PowerShell from the repository root unless stated. Never open or print `.env` files; the variable names are in the `*.example` files.

## Configuration files

| File | Read by | Variable names |
|---|---|---|
| `.env` (copy of [`.env.example`](../../.env.example)) | `docker-compose.v2.yml`; `eval/provider_check` (`--env-file`). `tests/tenant-isolation` reads no env file | Postgres passwords, MinIO accounts and S3 users, `SOPILOT_INTERNAL_TOKEN`, `SOPILOT_LLM_*`, optional `SOPILOT_GROQ_API_KEY`, `EMBEDDING_REVISION` |
| `services/core-api/.env` (copy of [`.env.example`](../../services/core-api/.env.example)) | core-api run from source | `GOOGLE_CLIENT_ID`, `SOPILOT_DB_*`, `SOPILOT_S3_*`, `SOPILOT_AI_BASE_URL`, `SOPILOT_INTERNAL_TOKEN` |
| `services/ai-service/.env` (copy of [`.env.example`](../../services/ai-service/.env.example)) | ai-service and worker run from source | `SOPILOT_DB_URL`, `SOPILOT_INTERNAL_TOKEN`, `SOPILOT_CORE_*`, `SOPILOT_S3_*`, `SOPILOT_LLM_*`, `EMBEDDING_REVISION` |

Values that must match across files are marked "same as" in the examples. Spring and pydantic do not read `.env` themselves; the examples contain the PowerShell line that loads a file into the current shell. `./scripts/check-env.ps1` checks the three files for missing keys, left-over placeholders and mismatched shared values, and prints keys and verdicts only, never values. Ask the owner for secret values; do not read them from the files.

## Steps

### 1. Start the infrastructure

```powershell
docker compose -f docker-compose.v2.yml up -d postgres flyway-core flyway-rag minio minio-init
```

The root `.env` must also set `SOPILOT_INTERNAL_TOKEN`, `SOPILOT_LLM_BASE_URL` and `SOPILOT_LLM_API_KEY` (any value) even for infrastructure only: compose checks the required variables of every service in the file, so a start of only these services still fails without them.

Expected: `postgres` and `minio` become healthy; `flyway-core`, `flyway-rag` and `minio-init` are one-shot and exit with code 0 (`docker compose -f docker-compose.v2.yml ps -a`). Host ports are bound to `127.0.0.1`: Postgres `55432` (`V2_POSTGRES_PORT`), MinIO API `59000` and console `59001` (`V2_MINIO_API_PORT`, `V2_MINIO_CONSOLE_PORT`). Flyway applies `infrastructure/db/migrations/core` and `rag`; `minio-init` creates the bucket `sopilot-v2-documents` and two users (core-api read/write, ai-service read-only).

### 2. Run the services from source

core-api (Java 21, port 8080):

```powershell
cd services/core-api
./mvnw spring-boot:run "-Dspring-boot.run.profiles=local"
```

ai-service API (port 8000) and the ingest worker, each in its own shell:

```powershell
cd services/ai-service
uv run --extra local --extra pdf uvicorn --app-dir src sopilot_ai.api.app:create_app --factory
```

```powershell
cd services/ai-service
$env:PYTHONPATH = "src"; uv run --extra local --extra pdf python -m sopilot_ai.worker
```

The `local` extra (sentence-transformers, embeddings) and the `pdf` extra (Docling) are not base dependencies; the container image installs both. Load the matching `.env` into each shell first (see above). Run long-lived processes in their own terminals or in the background. The first question builds the LLM and embedding providers; the first ingest downloads the embedding model from Hugging Face, so it is slow and needs network access.

With the `local` profile and no `SOPILOT_JWT_PRIVATE_KEY_PATH`, core-api creates the JWT signing key in memory, so restarting core-api invalidates every issued token; sign in again with dev login (`POST /api/v1/auth/dev-login`, see the [core-api README](../../services/core-api/README.md)). Data in Postgres and MinIO is kept.

### Alternative: everything in containers

`docker-compose.v2.yml` also defines `core-api`, `ai-service`, `ai-worker` and `web`. `docker compose -f docker-compose.v2.yml up -d --build` starts all of it. The `web` image is still wired to V1 until ticket V2-15; use the APIs, not the web UI. Do not run the container and the from-source copy of the same service together (same ports).

### 3. Seed demo data (optional)

```powershell
./scripts/seed-demo.ps1
```

Needs core-api running, plus ai-service and the worker so documents can reach `READY`. Idempotent; described in the root [README](../../README.md).

## Verify

- `docker compose -f docker-compose.v2.yml ps -a`: `postgres`, `minio` healthy; the three one-shot services exited 0.
- `GET http://localhost:8080/actuator/health` returns `UP` (no details).
- `GET http://localhost:8000/health` returns `{"status":"ok"}`. `{"status":"degraded","staleVersions":N}` means chunks were embedded by another model or revision: see [reindex](reindex.md).
- MinIO console on `http://127.0.0.1:59001` (root account from the root `.env`).

Services not reachable: [troubleshooting](troubleshooting.md).

## Roll back

Stop, keep the data:

```powershell
docker compose -f docker-compose.v2.yml down
```

Stop the from-source processes with Ctrl+C. Never add `-v`. Resetting data is an owner decision (the reset script is not run unless asked).
