---
title: "Quality gates"
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
---

# Quality gates

The checks a change passes, in order, and what each one does and does not prove. Layers and where evidence goes: [testing strategy](testing-strategy.md).

## 1. Per-scope checks (while working)

Run the narrowest check first, then the suite of the touched scope.

| Scope | Build / lint | Tests |
|---|---|---|
| core-api | `./scripts/validate-build.ps1 -Scope core` (`mvnw compile`) | `./scripts/run-tests.ps1 -Scope core-api -Type unit`; `-Type all` for the Docker-backed ITs |
| ai-service | `./scripts/validate-build.ps1 -Scope ai` (`compileall src`, `ruff check`) | `./scripts/run-tests.ps1 -Scope ai-service -Type unit\|integration\|all` |
| frontend | `./scripts/validate-build.ps1 -Scope web` (`pnpm build`, `pnpm lint`) | none exists; browser check by hand |
| schema | `./scripts/check-migrations.ps1` | `tests/tenant-isolation` (Docker) |
| docs | `./scripts/docs/check-docs.ps1` | n/a |

## 2. Pre-commit check

`./scripts/pre-commit-check.ps1` is run before proposing a commit. It reads the staged files (or the diff against `HEAD` when nothing is staged) and runs seven steps:

1. Lists the changed files.
2. Scans added lines (outside `scripts/`, `docs/` and `*.md`) for debug output (`console.log`, `System.out.println`, `print(`), hard-coded secrets, committed `.env` files, and `TODO`/`FIXME` without a ticket-style id.
3. For every touched `services/<name>/` and for `frontend/web/`, calls `run-tests.ps1` with the default `-Type all`. For `core-api` that is `mvnw verify`, so **Docker is needed** when core-api changed. For `ai-service` it runs all of `tests/`, integration included; without Docker those tests skip and the step still passes. Any touched frozen V1 service is tested too. For `frontend` the call errors because there is no `test` script (see the note below).
4. Validates `docker-compose.v2.yml` with `docker compose config` against `.env.example` (never `.env`); the frozen V1 `docker-compose.yml` only if the change touched it.
5. Runs `check-migrations.ps1`.
6. Runs the docs check (`check-docs.ps1`).
7. Prints the summary and exits non-zero if any step failed.

It does **not** run `ruff` or `validate-build.ps1`, the eval harness, the tenant-isolation suite or the browser checks.

Note on step 6: it currently calls `scripts/check-docs.ps1`, the old checker kept for the transition, not `scripts/docs/check-docs.ps1`. Switching it is planned and has not been done.

Note on step 3 for the frontend: `run-tests.ps1 -Scope frontend` raises an error when `package.json` has no `test` script, so a frontend change does not get through this step today. Run `validate-build.ps1 -Scope web` separately and record that the pre-commit step could not pass.

## 3. Continuous integration

`ci.yml` runs on pull requests and pushes to `main`/`develop`; `tenant-isolation.yml` runs on every pull request and on pushes to `main`/`develop`.

| Workflow | Jobs that gate V2 |
|---|---|
| `ci.yml` | `secret-scan`, `migrations`, `core-api-unit`, `ai-service-unit`; the frozen V1 jobs `backend-java`, `backend-python`, `frontend-and-gateway` (V1 until V2-17) |
| `tenant-isolation.yml` | `database`, `negative-control`, `core-api`, `ai-service`, `department-authorization` |
| docs job | **planned**, not present |

CI proves unit-level behaviour and the isolation claims (FR-19, FR-29). It does not run the full core-api IT set, the full ai-service integration set, the eval harness, a browser, or any live provider. See the table in [testing strategy](testing-strategy.md#what-runs-where).

## 4. Review

Before a non-trivial commit or PR, run the read-only agent `v2-reviewer` (`.claude/agents/v2-reviewer.md`) on the diff. It reports evidence-backed findings and never edits. Findings are fixed or answered before merging. It covers what automation does not: error text that leaks internals (constraint 6), tenant binding on new queries, contract drift between services, docs that describe the changed behaviour.

## 5. Ticket status

| Status | Meaning |
|---|---|
| `in_progress` | Work started |
| `review` | Code is committed; evidence is written and waits for the owner |
| `todo` / `blocked` | Not started / waiting; `blocked` requires `blocked_reason` |
| `done` | Evidence linked in the ticket ("Evidence": commands with results) **and** owner review |

Agents may propose `review` and `done`; the owner decides `done`. A status change updates the PLAN table and counters in the same edit (`completed` = done, `review` = review, `implemented` = done + review). Rules: [`docs/README.md`](../README.md#lifecycle).

## Not covered by any gate

Browser behaviour (Playwright is not installed), measured latency or quality on the research corpus (evaluated in `eval/`, reported in `docs/research/`), live Modal or Groq providers, and anything that needs Docker when Docker was not running. State these in the report instead of implying they passed.
