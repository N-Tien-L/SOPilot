# Tenant isolation (FR-19, V2-14)

Evidence that no workspace can read or change another workspace's data, run on every pull request by
[`.github/workflows/tenant-isolation.yml`](../../.github/workflows/tenant-isolation.yml).

| Layer | Where | What it proves |
|---|---|---|
| Database (this directory) | `test_db_isolation.py` | Three seeded workspaces, both application roles, **every** tenant table of `core` and `rag` found from the catalog: no/unknown/malformed workspace sees nothing, a workspace sees only its rows and none of another's secret strings, cannot insert/move/update/delete across tenants, the tenant never survives into the next transaction on a reused connection, roles are confined to their schema, SECURITY DEFINER helpers are not reachable from the other service |
| core-api HTTP | `services/core-api/.../tenancy/TenantIsolationApiIT.java` | Three workspaces with secrets in documents, departments, members, audit; every GET endpoint with admin and member tokens returns no foreign secret; every by-id attempt on another workspace's object is `404`; forged, edited, missing, expired tokens are `401`; one pooled connection is reused across requests; the application filter alone still holds with RLS off |
| ai-service retrieval | `services/ai-service/tests/integration/test_retrieval.py` | The access filter applies before `LIMIT` and never returns another workspace's chunks; delete removes everything |

Not covered yet, because the code does not exist: Q&A answers, conversations and feedback through the API (V2-10,
V2-13). Their tables are already covered by the database layer (`rag.conversations`, `messages`,
`message_feedback`, `message_citations`); add API-level cases here when those endpoints land. Department-level
authorization inside one workspace is V2-26.

```bash
cd tests/tenant-isolation
uv sync
uv run pytest -v                                      # needs Docker; starts a disposable pgvector Postgres
ISOLATION_MUTATION=disable-rls uv run pytest -q       # negative control: must FAIL
```

## Why a suite that can be shown to fail

`ISOLATION_MUTATION=disable-rls` turns row-level security off on every tenant table after seeding. A run that
still passes would mean the suite looks at nothing; CI requires this run to be red. `test_detector_*` additionally
create a throwaway table without RLS and check the detectors flag it, then turn RLS on and check they go quiet.
At the API layer the same was checked by hand on 2026-11-06: removing the `workspace_id` predicate from the document
list query **and** disabling RLS made `TenantIsolationApiIT` fail with "workspace A leaked a secret of B".

## Adding a table

A new table with a `workspace_id` column is picked up automatically and must have `ENABLE` + `FORCE ROW LEVEL SECURITY`
and a policy tied to `current_workspace()`. A new table without `workspace_id` fails
`test_only_reviewed_tables_are_global` until it is added to `GLOBAL_TABLES` in `isolation.py` with a reason.
