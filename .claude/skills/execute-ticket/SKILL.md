---
name: execute-ticket
description: Implement a planned SOPilot ticket (docs/execution/initiatives/<initiative>/tickets/, e.g. V2-NN or TICKET-NNN) end to end with an agent team: Opus orchestrator, Sonnet coders per work packet, Haiku runners for commands, and a fresh Opus reviewer. Covers dependency check, branch, service → frontend order, tests, review, doc reconciliation, and ticket/PLAN status with evidence. Use when the user says "implement/làm/triển khai V2-NN" or picks up a ticket. Not for one-line fixes or doc-only edits.
---

# Execute a ticket

## 0. The team

| Role | Who | Model / effort | Owns |
|---|---|---|---|
| Orchestrator | this session | latest Opus | reading, plan, frozen contracts, packets, migrations and RLS/tenant paths (or line-by-line check of them), integration, pass/fail, docs, ticket/PLAN status, git |
| Coder | `v2-coder` | `model: "sonnet"`, `effort: "medium"` (`"high"` for concurrency, outbox, retrieval ranking) | one work packet: its files, its tests, its narrow checks |
| Runner | `v2-runner` | `model: "haiku"`, `effort: "low"` | long or noisy commands, searches and inventories; raw results only |
| Reviewer | `v2-reviewer` | `model: "opus"`, `effort: "high"` | independent review, new instance each round |

- Always pass the model aliases `"opus"`, `"sonnet"`, `"haiku"` (they track the latest: at the time of writing `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`). Never pin an older id. Every agent states its model id first; tell the owner if one is not the latest.
- The orchestrator never reviews its own final diff in place of `v2-reviewer`: two Opus roles, two contexts.
- Hooks enforce the roles (`guard.py --coder`, `--runner`, `--readonly`). A blocked call from a subagent comes back to you as a report; decide it yourself or ask the owner. Never ask a subagent to work around a block.
- Skip the team for a small ticket (one file, no contract change, under ~50 lines): do it yourself and still use a fresh reviewer if the diff is non-trivial.

## 1. Read before writing (orchestrator)

1. Ticket `docs/execution/initiatives/<initiative>/tickets/<ID>-*.md` (V2 MVP: `v2-sopilot-mvp`): frontmatter (`scope`, `depends_on`, `branch`, `status`), acceptance criteria, implementation notes. The initiative README lists its PRD, designs and ADRs.
2. Every `depends_on` ticket must be `done` (or `review` if the owner said so). Otherwise stop and report the blocker.
3. Read the design section the ticket cites (`TECH-V2-core-api` = `docs/architecture/components/core-api.md`, `TECH-V2-ai-service` = `components/ai-service.md`), the matching rule in `.claude/rules/`, and the actual code path you will change. Never treat a stub as wired. Broad inventories ("every caller of X", "every endpoint using Y") may go to a `v2-runner`; read the hits that matter yourself.
4. Note any doc/code disagreement. Code wins; report it, do not quietly align either side.

## 2. Plan and packets

- Write a short plan and show it: files, tests per acceptance criterion, risks, docs to update (for multi-service, contract or schema changes also: migration via skill `flyway-migration`, endpoints, tenant-isolation impact). Stop for owner approval before adding a dependency that is not already approved or changing a contract.
- Order: migration → core-api → ai-service → frontend → docs. Cross-service calls follow the existing pattern: core-api → ai-service via outbox (`OutboxDispatcher`), ai-service → core-api via `/internal/**` callbacks with `X-Internal-Token`, browser → each service with the core-api access token (ai-service verifies through JWKS).
- Freeze the contracts first (endpoint, status codes, payload shape, columns, signatures), then split the work into packets using [packet-template.md](packet-template.md). One packet = one coherent slice, normally one service, with its own tests. Every acceptance criterion belongs to exactly one packet.
- Keep for yourself: Flyway migrations, RLS policies and grants, `TenantTx`/`tenant_tx` wiring, and anything where a packet would be shorter than its explanation. Dependency manifests are always yours, after owner agreement.
- Show the packet list (id, goal, files, model/effort) with the plan.

## 3. Branch and status (orchestrator)

- Inspect `git status` first. Do not touch unrelated uncommitted files; list them in each packet's "Read only" if they are nearby.
- Branch from `develop` using the ticket's `branch` field or `{type}/{scope}-{short-name}`. Never `main`.
- Set the ticket `status: in_progress` and `updated:`. Leave PLAN counters alone until `review`.

## 4. Implement

- Coders work in this checkout, one at a time, in the order above. No worktrees by default: `develop` often has uncommitted work that a worktree would not see. Run two coders in parallel only if their "May edit" sets are disjoint and every contract between them is frozen.
- Spawn: `Agent(subagent_type: "v2-coder", model: "sonnet", effort: <per table>, prompt: <filled packet>)`. Remember its id for fix rounds.
- After each packet: read its report, then read the actual diff of its files (`git diff -- <files>` plus new files). Check scope, the frozen contract and the hard limits. If it went outside "May edit", revert only those hunks yourself or send a fix round.
- Fix rounds go to the **same** coder via `SendMessage` (fix-round format in the template) so it keeps its context. If a coder fails the same check twice, or reports `blocked`, take the packet over yourself or re-plan; do not spawn a third attempt.
- Every tenant-scoped path: core-api `tenant.run(principal, ...)`, ai-service `tenant_tx(...)`, plus an isolation test case. New env var: `.env.example` with a dummy value. Never read `.env`.

## 5. Verify (record command + result for the report)

| Touched | Command |
|---|---|
| core-api | `./scripts/run-tests.ps1 -Scope core-api -Type unit`; then `-Type all` (Docker) for anything touching SQL, tenancy or HTTP |
| ai-service | `./scripts/validate-build.ps1 -Scope ai`; `./scripts/run-tests.ps1 -Scope ai-service -Type unit`; `-Type integration` (Docker) for SQL/retrieval |
| migrations | `./scripts/check-migrations.ps1` + the integration suites above + `tests/tenant-isolation` |
| frontend | `./scripts/validate-build.ps1 -Scope web`, plus a browser check if UI changed (say if not done) |
| retrieval ranking | `cd eval; uv run pytest -q` |
| before proposing a commit | `./scripts/pre-commit-check.ps1` |

- Scope suites run after all packets are in, delegated to `Agent(subagent_type: "v2-runner", model: "haiku", effort: "low")`, one command per block in its prompt, with the cwd. The runner refuses `uv sync` without `--locked` (it must not rewrite lockfiles): pass `uv sync --extra dev --locked`, or sync yourself first. Independent suites (e.g. core-api unit and frontend build) may run as parallel runners.
- You decide pass/fail from the exit code. For any failure or surprise, re-run the narrow command yourself and read the raw output. Coder and runner reports are claims: the ticket's Evidence section takes only output you have seen yourself (runner blocks quoted verbatim count; a summary does not).
- Do not use a runner for short commands, edits, judgments or reviews. Use skill `testing` for writing tests and triaging failures.

## 6. Review

- `git diff`: scope creep, debug output, secrets, TODO without a ticket id.
- For non-trivial diffs, spawn a **fresh** `v2-reviewer` (new agent each round, never resumed) with `model: "opus"`, `effort: "high"`. Give it only: the ticket path, the diff scope (`git diff <base>..HEAD` plus untracked files, or the exact file list), the rules to check, and "form your own judgment; do not assume the implementer is right". Do not paste your own or the coders' conclusions.
- Triage each finding yourself. Accepted BLOCKER/WARNING findings go back to the coder that owns the file (fix round), or you fix them if the code is yours. If there was a BLOCKER, run a second fresh reviewer on the new diff. At most two rounds; list anything left open in the report. The reviewer cannot run `uv` scripts, so run `./scripts/docs/check-docs.ps1` and the plan check yourself (or via a runner).

## 7. Docs and status (orchestrator)

- Reconcile docs with what was built (`docs/README.md`, "Which document, if any"). Endpoint, schema, RBAC or flow changed → update the design section, `docs/architecture/domain/identity-and-access.md`, `docs/architecture/data/{core,rag}-schema.md` or `docs/architecture/api/http-conventions.md` as relevant, and the `services/<svc>/README.md` endpoint/env tables. Mark anything still planned as planned. Skill `project-docs` for ids and validation. A packet may carry a doc edit when the text is fully specified; status files never.
- Ticket → `review` when code is committed and the evidence is listed in its "Evidence" section. Update the PLAN status table and the counters `review_tickets` and `implemented_tickets` in the same edit (definitions in `docs/README.md`), then run `./scripts/docs/check-docs.ps1` and `cd eval; uv run pytest -q tests/test_review_regressions.py -k plan`. **Never set `done`.** That needs owner review of the evidence.
- Do not commit or push until the owner asks. Then: Conventional Commits `<type>(<scope>): <summary> (<ticket id>)`, no AI attribution.

## Done when

Every acceptance criterion maps to a passing test or a recorded command output that you have seen. Docs and status are updated. The report lists: files changed (per packet), commands and results, reviewer findings and how each was resolved, what was not verified, docs updated, risks, the team actually used (packets, models, fix rounds, takeovers) and a proposed commit message.

## If blocked

A dependency is not done, the spec is ambiguous, an owner decision is needed, a coder reports an open question you cannot answer from the docs or code, or a check fails for reasons outside the ticket. Stop, keep the work in the tree, and report exactly what is missing. Do not widen scope to unblock yourself or a coder.
