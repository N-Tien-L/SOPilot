# V2 database and storage (`docker-compose.v2.yml`)

Local infrastructure for SOPilot V2 (ADR-004 §4.4, ticket V2-08). It runs as a separate compose project, `sopilot-v2`, with its own volumes and network, so it never touches the legacy stack (`docker-compose.yml`, `infrastructure/init-db/`).

## Start

1. Copy the "V2" block of `.env.example` into `.env` and replace every `<generate-...>` value.
2. Start it:

   ```powershell
   docker compose -f docker-compose.v2.yml up -d
   ```

   `flyway-core`, `flyway-rag` and `minio-init` run once and exit with code 0.
3. Stop it without deleting data: `docker compose -f docker-compose.v2.yml down` (never add `-v`).

Published ports, bound to `127.0.0.1` only: Postgres `55432`, MinIO API `59000`, MinIO console `59001` (change with `V2_POSTGRES_PORT`, `V2_MINIO_API_PORT`, `V2_MINIO_CONSOLE_PORT`).

## Roles

Created once by `init/01-roles.sh` on a fresh volume:

| Role | Used by | Rights |
|---|---|---|
| `postgres` | Container superuser | Only for `init/` and emergencies |
| `sopilot_migrator` | Flyway | Owns schemas `core` and `rag` and every table in them |
| `sopilot_core_app` | core-api | DML on `core` only; owns nothing; `NOBYPASSRLS` |
| `sopilot_ai_app` | ai-service | DML on `rag` only; owns nothing; `NOBYPASSRLS` |

Because the application roles do not own tables, row-level security (`FORCE ROW LEVEL SECURITY`) applies to them. Each role can only read and write its own service's schema.

The `vector` extension is created by the superuser in `public`.

## Migrations

Flyway runs one version chain per schema, each with its own history table:

| Folder | Schema | History table |
|---|---|---|
| `migrations/core/` | `core` | `core.flyway_schema_history` |
| `migrations/rag/` | `rag` | `rag.flyway_schema_history` |

Rules:
- Name files `V<NNN>__<snake_case>.sql`, numbered in sequence within each folder. Never edit a migration that has already run; add a new one.
- Additive changes only. No `DROP SCHEMA`, `TRUNCATE` or `DROP DATABASE`.
- New tables are covered automatically by the default privileges from `V001` (DML for the service's app role). Tables with `workspace_id` must `ENABLE` and `FORCE ROW LEVEL SECURITY` with a policy on `<schema>.current_workspace()`.
- Functions are not executable by `PUBLIC`; grant `EXECUTE` explicitly. `SECURITY DEFINER` helpers must `SET search_path = <schema>, pg_temp`.
  Both `V002__explicit_function_grants.sql` migrations repair V001's schema-local
  default revoke: the global PUBLIC EXECUTE default must be revoked globally for
  `sopilot_migrator`. The chains serialize this shared change with a transaction
  advisory lock. Existing explicit app-role grants remain.
- Update `.agent/context/database/` when a migration adds or changes tables.

`init/` scripts only run on an empty volume. Role or extension changes on an existing volume need an explicit, reviewed SQL run.

V002 was exercised only on disposable verification databases on 2026-10-24;
it has not been applied to the owner's persistent database. Existing V2 databases
receive it by running the two Flyway services normally, without resetting volumes
or editing already-applied V001 files.

## Object storage

`../storage/minio-init.sh` creates the bucket `SOPILOT_S3_BUCKET` (default `sopilot-v2-documents`) with no anonymous access, a read/write user for core-api (`SOPILOT_S3_ACCESS_KEY`) and a read-only user for ai-service (`SOPILOT_S3_AI_ACCESS_KEY`). Both services read the same bucket name from env.

Policy attachment errors fail initialization rather than reporting readiness.

## Isolated verification (no .env)

From `eval/`: `./.venv/Scripts/python.exe -m sopilot_eval.infra_check`.
Checks Flyway, role/schema isolation, RLS, explicit function grants and S3 privileges
in a unique project using tmpfs and random credentials. No existing volume is
mounted or deleted. Scope and limits are recorded in
`docs/04-reports/AUDIT-v2-05-v2-08-acceptance-2026-10-25.md`.

## Check

```powershell
docker compose -f docker-compose.v2.yml ps -a
docker exec sopilot-v2-postgres psql -U postgres -d sopilot -c "\du"
docker exec sopilot-v2-postgres psql -U postgres -d sopilot -c "SELECT version, description, success FROM core.flyway_schema_history UNION ALL SELECT version, description, success FROM rag.flyway_schema_history"
```
