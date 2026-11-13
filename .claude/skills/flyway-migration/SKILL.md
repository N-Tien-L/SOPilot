---
name: flyway-migration
description: Add a V2 Flyway migration to infrastructure/db/migrations/core or /rag (new table, column, index, policy, function or grant), with RLS, grants, verification and doc updates. Use whenever a V2 ticket changes the core or rag schema. Not for V1 infrastructure/init-db (frozen).
---

# Add a V2 Flyway migration

Constraints are in `.claude/rules/migrations.md` (loaded with any `infrastructure/db/**` file) and `infrastructure/db/README.md`. This skill is the procedure.

## 1. Decide the chain and the version

- `core/` if core-api owns the data, `rag/` if ai-service owns it (ADR-004). Never write the other service's schema. Cross-service data travels by HTTP or outbox.
- Next version = highest `V<NNN>` in that chain + 1, three digits: `V006__department_visibility.sql`. Check with `./scripts/check-migrations.ps1`.
- If the change "fixes" an existing migration, it is still a new file. The hook blocks editing committed migrations.

## 2. Write the SQL

Start from `references/template.sql`. Checklist:

- [ ] Header comment: ticket id and TECH section (`-- V2-24: ... (TECH-V2-core-api §5.5)`).
- [ ] Additive only: `CREATE`/`ALTER ... ADD`. A rename or drop needs an owner decision and an expand/contract plan, not a single migration.
- [ ] A table with `workspace_id`: `ENABLE` + `FORCE ROW LEVEL SECURITY` and policy `tenant_isolation` on `<schema>.current_workspace()` (USING and WITH CHECK). Composite FKs or `workspace_id` on child rows, so a join cannot cross workspaces.
- [ ] DML for the app role comes from V001 default privileges. Revoke what it must not do (for example `REVOKE UPDATE, DELETE` on append-only tables).
- [ ] New function: `REVOKE EXECUTE ... FROM PUBLIC`, then `GRANT EXECUTE ... TO sopilot_<core|ai>_app`. `SECURITY DEFINER` also needs `SET search_path = <schema>, pg_temp` and, if it reads FORCE-RLS tables, a `definer_access` policy `TO sopilot_migrator` on just those tables.
- [ ] Index every FK and every `workspace_id` + filter column used by a query.

## 3. Verify (run, do not assume)

1. `./scripts/check-migrations.ps1` must pass.
2. Apply the chain to a disposable database through the integration suites. They run `init/01-roles.sh` and both chains as `sopilot_migrator`, then connect as the app role:
   - core: `./scripts/run-tests.ps1 -Scope core-api -Type all` (Docker)
   - rag: `./scripts/run-tests.ps1 -Scope ai-service -Type integration` (Docker)
3. Run the database isolation suite: `cd tests/tenant-isolation; uv run pytest -v` (Docker). It discovers tables from the catalog. A new tenant table is covered automatically and must pass the RLS checks. A new table without `workspace_id` fails `test_only_reviewed_tables_are_global` until it is listed there on purpose, which needs owner review.
4. Never apply to the owner's persistent `sopilot-v2` volume yourself. Tell the user to run `docker compose -f docker-compose.v2.yml up flyway-core flyway-rag` (or the matching service) when they are ready.

## 4. Update docs in the same change

- `docs/architecture/data/core-schema.md` or `rag-schema.md`: table, columns, RLS, grants (append; keep the per-migration layout).
- The design section only if the design changed (owner approval). Ticket notes: the migration file name.

## Done when

The check script passes; the integration suite that applies the chain passes; the schema doc is updated; the report names the file, the commands run with their results, and anything not verified (for example "not applied to the persistent volume").

## If something fails

- Checksum or "migration modified" error: you edited an existing file. Restore it and move the change to a new version.
- `permission denied` as the app role: missing grant or policy. Fix it in the new migration. Never grant `BYPASSRLS` or table ownership to an app role.
- A Testcontainers failure that is not SQL (Docker not running): report it as unverified; do not skip the step silently.
