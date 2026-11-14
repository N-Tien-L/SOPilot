---
name: execute-ticket
description: Implement a planned SOPilot ticket (docs/execution/initiatives/<initiative>/tickets/, e.g. V2-NN or TICKET-NNN) end to end. Covers dependency check, branch, service → frontend order, tests, self-review, doc reconciliation, and ticket/PLAN status with evidence. Use when the user says "implement/làm/triển khai V2-NN" or picks up a ticket. Not for one-line fixes or doc-only edits.
---

# Execute a ticket

## 1. Read before writing

1. Ticket `docs/execution/initiatives/<initiative>/tickets/<ID>-*.md` (V2 MVP: `v2-sopilot-mvp`): frontmatter (`scope`, `depends_on`, `branch`, `status`), acceptance criteria, implementation notes. The initiative README lists its PRD, designs and ADRs.
2. Every `depends_on` ticket must be `done` (or `review` if the owner said so). Otherwise stop and report the blocker.
3. Read the design section the ticket cites (`TECH-V2-core-api` = `docs/architecture/components/core-api.md`, `TECH-V2-ai-service` = `components/ai-service.md`) and the matching rule in `.claude/rules/` (it loads when you open files in that service). Then read the actual code path you will change. Never treat a stub as wired.
4. Note any doc/code disagreement. Code wins; report it, do not quietly align either side.

## 2. Plan

- More than one service, or any contract/schema change: write a short plan first. List files, migration (skill `flyway-migration`), endpoints, the tenant-isolation impact, the tests that prove each acceptance criterion, and the docs to update.
- Order: migration → core-api → ai-service → frontend → docs. Cross-service calls follow the existing pattern: core-api → ai-service via outbox (`OutboxDispatcher`), ai-service → core-api via `/internal/**` callbacks with `X-Internal-Token`, browser → each service with the core-api access token (ai-service verifies through JWKS).

## 3. Branch and status

- Inspect `git status` first. Do not touch unrelated uncommitted files.
- Branch from `develop` using the ticket's `branch` field or `{type}/{scope}-{short-name}`. Never `main`.
- Set the ticket `status: in_progress` and `updated:`. Leave PLAN counters alone until `review`.

## 4. Implement

- Make the smallest change that meets each acceptance criterion. No drive-by refactors or renames of `poliwise` legacy names.
- Every tenant-scoped path: core-api `tenant.run(principal, ...)`, ai-service `tenant_tx(...)`, plus an isolation test case.
- New env var: add it to `.env.example` with a dummy value. Never read `.env`.

## 5. Verify (record command + result for the report)

| Touched | Command |
|---|---|
| core-api | `./scripts/run-tests.ps1 -Scope core-api -Type unit`; then `-Type all` (Docker) for anything touching SQL, tenancy or HTTP |
| ai-service | `./scripts/validate-build.ps1 -Scope ai`; `./scripts/run-tests.ps1 -Scope ai-service -Type unit`; `-Type integration` (Docker) for SQL/retrieval |
| migrations | `./scripts/check-migrations.ps1` + the integration suites above + `tests/tenant-isolation` |
| frontend | `./scripts/validate-build.ps1 -Scope web`, plus a browser check if UI changed (say if not done) |
| retrieval ranking | `cd eval; uv run pytest -q` |
| before proposing a commit | `./scripts/pre-commit-check.ps1` |

Use skill `testing` for writing tests and triaging failures.

## 6. Self-review

- `git diff`: scope creep, debug output, secrets, TODO without a ticket id, edits to V1 paths.
- For non-trivial diffs, delegate to the `v2-reviewer` agent (read-only) and address BLOCKERs.

## 7. Docs and status

- Reconcile docs with what was built (`docs/README.md`, "Which document, if any"). Endpoint, schema, RBAC or flow changed → update the design section, `docs/architecture/domain/identity-and-access.md`, `docs/architecture/data/{core,rag}-schema.md` or `docs/architecture/api/http-conventions.md` as relevant, and the `services/<svc>/README.md` endpoint/env tables. Mark anything still planned as planned. Skill `project-docs` for ids and validation.
- Ticket → `review` when code is committed and the evidence is listed in its "Evidence" section. Update the PLAN status table and the counters `review_tickets` and `implemented_tickets` in the same edit (definitions in `docs/README.md`), then run `./scripts/docs/check-docs.ps1` and `cd eval; uv run pytest -q tests/test_review_regressions.py -k plan`. **Never set `done`.** That needs owner review of the evidence.
- Commit only when asked: Conventional Commits `<type>(<scope>): <summary> (<ticket id>)`, no AI attribution.

## Done when

Every acceptance criterion maps to a passing test or a recorded command output. Docs and status are updated. The report lists files changed, commands and results, what was not verified, and the docs updated.

## If blocked

A dependency is not done, the spec is ambiguous, an owner decision is needed, or a check fails for reasons outside the ticket. Stop, keep the work in the tree, and report exactly what is missing. Do not widen scope to unblock yourself.
