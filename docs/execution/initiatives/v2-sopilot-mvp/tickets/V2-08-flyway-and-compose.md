---
id: V2-08
title: "Flyway and docker compose skeleton (Postgres/pgvector, object storage)"
type: chore
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: infra
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-01]
blocks: [V2-09, V2-11]
branch: "chore/infra-v2-compose"
assignee: pair
---

# TICKET V2-08: V2 base infrastructure

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
A new database (ADR-004 §4.4), Flyway migrations in `infrastructure/db/migrations/`, running locally and in CI. The old volumes are not touched.

## 2. Acceptance criteria
- [x] `docker-compose.v2.yml` (a separate file, the old compose unchanged): Postgres 16 + pgvector (pinned), pinned S3 object storage (pinned MinIO or SeaweedFS, per V2-01), one-shot Flyway containers.
- [x] Three DB roles per TECH-V2-core-api §4.1: `sopilot_migrator` (owner of schemas `core` and `rag`), `sopilot_core_app` (only `core`), `sopilot_ai_app` (only `rag`); the two application roles own no tables and are `NOBYPASSRLS`, so RLS takes effect. Test: `sopilot_ai_app` cannot read `core` tables and vice versa.
- [x] Migration `V001` creates schemas `core`, `rag`, the `vector` extension (pgvector ≥ 0.8), the functions `core.current_workspace()` / `rag.current_workspace()` and default grants; a sample migration runs cleanly on an empty DB. Business tables are not part of this ticket: `rag.*` tables are written by `V2-09` (and `V2-13`, `V2-25` for their own), `core.*` tables by `V2-11`, `V2-12`, `V2-23`, `V2-24`.
- [x] Only the ports needed locally are published; secrets come from `.env`, and `.env.example` has dummy values.
- [x] Fully separate from the old stack (ADR-004 §4.5). The old `docker-compose.yml` declares no `name:`, so its default project is `sopilot`, its volume `sopilot_postgres_data`, its container `sopilot-postgres`. `docker-compose.v2.yml` must set `name: sopilot-v2`; containers (if named) are prefixed `sopilot-v2-`; volumes use their own keys (for example `v2_postgres_data`, `v2_object_data`). Check: after `up`, `docker volume ls` shows no old volume mounted into a V2 container. *(Configuration: `name: sopilot-v2`, containers `sopilot-v2-*`, volumes `sopilot-v2_postgres_data`/`sopilot-v2_minio_data`; the 2026-10-20 check used tmpfs, so `docker volume ls` has not been run with the real `.env`.)*
- [x] Host ports do not clash with the old stack (which uses `3000`, `3001`). The V2 port table is in `infrastructure/db/README.md`. Dev convention: one stack at a time; start the old stack only to compare or port code. *(Postgres `55432`, MinIO `59000`/`59001`, bound only to `127.0.0.1`.)*
- [x] No `docker compose down -v` or volume reset.

## 3. Guide
- **Files:** `docker-compose.v2.yml`, `infrastructure/db/migrations/V001__*.sql`, `infrastructure/db/README.md`, `.env.example` (CREATE).

## 4. Testing
`docker compose -f docker-compose.v2.yml up -d`, then query `flyway_schema_history` and `\du`; `docker volume ls` to confirm the V2 volumes are separate from the old `sopilot_*` volumes. Record commands and results.

### Results 2026-10-20
Run on a temporary project `sopilot-v2-verify` with an env file of random passwords and a tmpfs data override, so no volume was created and the real `.env` was not touched:
- `up -d`: `postgres`, `minio` healthy; `flyway-core`, `flyway-rag`, `minio-init` exit 0.
- Roles: `sopilot_migrator`, `sopilot_core_app`, `sopilot_ai_app` all `rolsuper = f`, `rolbypassrls = f`. Schemas `core`, `rag` owned by `sopilot_migrator`; extension `vector` 0.8.0.
- `core.flyway_schema_history` and `rag.flyway_schema_history` both have `001` with `success = t`.
- RLS probe (in one transaction, then rolled back): `sopilot_core_app` sees only the rows of the workspace set; with the variable unset → 0 rows; writing a row of another workspace → `new row violates row-level security policy`; reading `rag` → `permission denied for schema rag`; creating a table in `core` → `permission denied`; `sopilot_ai_app` reading `core` → `permission denied for schema core`.
- MinIO: bucket `sopilot-v2-documents` denies anonymous access; users `sopilot-core` (read/write) and `sopilot-ai` (read-only).
- Stopped with `down` (no `-v`); no container or volume of the temporary project is left.

Note: `.env.example` already existed, so the V2 variable block was appended instead of creating a new file. V2 variables use the `V2_`/`SOPILOT_S3_` prefixes so they do not touch the old stack's variables. The stack has not been run with the owner's real `.env`.

### Review 2026-10-24
Added `V002__explicit_function_grants.sql` for both schemas to revoke the migrator's global default EXECUTE and fix the helpers already created; V001 is not edited. A failing MinIO policy attach must fail the init. Automated verification with `eval/sopilot_eval/infra_check.py` on a separate project, random passwords, tmpfs, no `.env` read: Flyway/RLS/schema/function grants/S3 pass. No migration applied to the owner's DB; the persistent volume and real `.env` remain unchecked. The delta was not yet committed/reviewed, so kept `review`. See [AUDIT readiness](../../../../archive/reports/AUDIT-v2-readiness-preparation-2026-10-24.md).

### Acceptance 2026-10-25
The owner settled the scope in chat ("ok chốt"). Accepts the local infrastructure: V2 volume/network configuration separate from V1, loopback ports; Flyway, RLS, S3 and repeated init checked on a tmpfs project. No `.env` read, no existing volume mounted/reset, no migration applied to the owner's DB. See the [acceptance record](../../../../quality/test-reports/audit-v2-05-v2-08-acceptance-2026-10-25.md).
