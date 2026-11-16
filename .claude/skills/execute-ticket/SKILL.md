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

- Always write a short plan before coding and show it: files, tests per acceptance criterion, risks, docs to update (for multi-service, contract or schema changes also: migration via skill `flyway-migration`, endpoints, tenant-isolation impact). Stop for owner approval before adding a dependency that is not already approved or changing a contract.
- Subagent models: always the latest Haiku and Opus. Pass the aliases `model: "haiku"` / `"opus"` (they track the latest; at the time of writing `claude-haiku-5-5` and `claude-opus-5-5`) and never pin an older id. If a subagent reports an older model, tell the owner.
- Order: migration → core-api → ai-service → frontend → docs. Cross-service calls follow the existing pattern: core-api → ai-service via outbox (`OutboxDispatcher`), ai-service → core-api via `/internal/**` callbacks with `X-Internal-Token`, browser → each service with the core-api access token (ai-service verifies through JWKS).

## 3. Branch and status

- Inspect `git status` first. Do not touch unrelated uncommitted files.
- Branch from `develop` using the ticket's `branch` field or `{type}/{scope}-{short-name}`. Never `main`.
- Set the ticket `status: in_progress` and `updated:`. Leave PLAN counters alone until `review`.

## 4. Implement

- Make the smallest change that meets each acceptance criterion. No drive-by refactors or renames.
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

Long or noisy commands (build, lint, test, docker logs, repo-wide search) may go to a `general-purpose` subagent with `model: "haiku"`. Its prompt names the exact command and requires this reply only: (1) command, (2) exit code, (3) failing items verbatim (file:line, test name, message), (4) last 20 lines, (5) one line `unverified:`. It must not edit files, run other commands, open `.env`, or give opinions. You decide pass/fail from the exit code, re-read the raw output yourself for any failure or surprise, and record in the ticket only evidence from real command output, never a Haiku summary alone. Do not use it for short commands, edits, judgments or reviews.

Use skill `testing` for writing tests and triaging failures.

## 6. Self-review

- `git diff`: scope creep, debug output, secrets, TODO without a ticket id.
- For non-trivial diffs, spawn a **fresh** `v2-reviewer` (new agent each time, never resumed) with `model: "opus"`. Give it only: the ticket path, the diff scope (`git diff <base>..HEAD` plus untracked files), the rules to check, and "form your own judgment; do not assume the implementer is right". Do not paste your own conclusions. Ask it to state its model id first and tell the owner if it is not the latest Opus.
- Fix every BLOCKER and WARNING you accept. If there was a BLOCKER, run a second fresh reviewer on the new diff. At most two rounds; list anything left open in the report. The reviewer cannot run `uv` scripts, so run `./scripts/docs/check-docs.ps1` and the plan check yourself.

## 7. Docs and status

- Reconcile docs with what was built (`docs/README.md`, "Which document, if any"). Endpoint, schema, RBAC or flow changed → update the design section, `docs/architecture/domain/identity-and-access.md`, `docs/architecture/data/{core,rag}-schema.md` or `docs/architecture/api/http-conventions.md` as relevant, and the `services/<svc>/README.md` endpoint/env tables. Mark anything still planned as planned. Skill `project-docs` for ids and validation.
- Ticket → `review` when code is committed and the evidence is listed in its "Evidence" section. Update the PLAN status table and the counters `review_tickets` and `implemented_tickets` in the same edit (definitions in `docs/README.md`), then run `./scripts/docs/check-docs.ps1` and `cd eval; uv run pytest -q tests/test_review_regressions.py -k plan`. **Never set `done`.** That needs owner review of the evidence.
- Do not commit or push until the owner asks. Then: Conventional Commits `<type>(<scope>): <summary> (<ticket id>)`, no AI attribution. The final report adds reviewer findings and how each was resolved, risks, and a proposed commit message.

## Done when

Every acceptance criterion maps to a passing test or a recorded command output. Docs and status are updated. The report lists files changed, commands and results, what was not verified, and the docs updated.

## If blocked

A dependency is not done, the spec is ambiguous, an owner decision is needed, or a check fails for reasons outside the ticket. Stop, keep the work in the tree, and report exactly what is missing. Do not widen scope to unblock yourself.
