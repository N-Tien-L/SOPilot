---
paths:
  - "infrastructure/db/**"
---

# V2 Flyway migrations (`infrastructure/db/migrations/{core,rag}`)

Full rules and roles: `infrastructure/db/README.md`. Procedure for a new migration: skill `flyway-migration`.

- One chain per schema. Files are `V<NNN>__<snake_case>.sql`, numbered 1..n without gaps **within each chain**.
- Never edit, rename or delete a committed migration: Flyway checksums break on every database that already ran it. Add the next version instead. The PreToolUse hook blocks file-tool edits and shell writes (redirects, `sed -i`, `mv`, `rm`, ...) to files in `HEAD`, also from a git worktree.
- Additive only. No `DROP SCHEMA/DATABASE/TABLE`, no `TRUNCATE`.
- Tables with `workspace_id`: `ENABLE` + `FORCE ROW LEVEL SECURITY` with a policy on `<schema>.current_workspace()`. Functions: no `PUBLIC` execute, explicit `GRANT EXECUTE`. `SECURITY DEFINER` requires `SET search_path = <schema>, pg_temp`.
- `init/` scripts run only on an empty volume. Role changes on an existing volume need an explicit reviewed SQL run, never a volume reset.
- Check: `./scripts/check-migrations.ps1` (naming, gaps, immutability vs `HEAD` and `main`, destructive DDL; also part of `pre-commit-check.ps1`). Behaviour proof: `./scripts/run-tests.ps1 -Scope core-api -Type all` and `-Scope ai-service -Type integration`. Both apply the chains to a disposable Postgres. Then update `docs/architecture/data/{core,rag}-schema.md`.
