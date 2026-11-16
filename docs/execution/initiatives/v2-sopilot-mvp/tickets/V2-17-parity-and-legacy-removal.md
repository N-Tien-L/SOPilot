---
id: V2-17
title: "Parity check, remove the 8 old services, update guidance docs"
type: chore
status: in_progress
created: 2026-10-17
updated: 2026-11-17
author: "Owner"
scope: platform
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-14, V2-15, V2-16, V2-26, V2-31, V2-32, V2-33, V2-42]
blocks: [V2-18]
branch: "chore/infra-remove-legacy"
assignee: pair
---

# TICKET V2-17: Parity and removing the old code

> Translated from Vietnamese on 2026-11-13. Since the 2026-11-13 docs restructure, the V1 context docs live as an archived snapshot in `docs/archive/v1-context/`, and the V2 context lives in `docs/architecture/`.
>
> **Pre-execution audit 2026-11-16 (on `develop` at `662eac2`):** every dependency (`V2-14`, `V2-15`, `V2-16`, `V2-26`, `V2-31`, `V2-32`, `V2-33`) is `done`, and so are `V2-39` and `V2-41`, which are not dependencies. The parity scope widens from UC-01–UC-11 to **UC-01–UC-12**, matching PRD-V2 §7. The cleanup targets, scripts, CI jobs and docs below were checked against the tree. The branch changes from `chore/platform-remove-legacy` to `chore/infra-remove-legacy`, because `platform` is not one of the CLAUDE.md commit/branch scopes. No dependency, status or counter changes.

## 1. Context & goal
V2 has to reach parity with PRD-V2 before the V1 stack is removed. The removal goes in its own commit, separate from the parity record and the reference updates, so the history stays clear. Git history and the `v1-final` tag keep V1.

State on `develop` (2026-11-16):
- **The V1 frontend is already gone.** V2-38 removed the V1 pages, components, stores, services and the dependencies only they used, and rebuilt `frontend/web` on Next.js 16 + TanStack Query v5 + Vitest. V2-15/V2-31/V2-32/V2-33 then built the V2 screens on it. This ticket deletes nothing under `frontend/web`. It only fixes docs that still say the frontend is "V1-wired".
- **`v1-final` exists and is pushed.** It was created in V2-38 at `835cf28`, pushed to `origin` on 2026-11-15, and is an ancestor of `develop`. Every V1 path listed in §2.3 is byte-identical between `v1-final` and `develop` (`git diff --stat v1-final develop -- <V1 paths>` is empty). The tag is therefore an exact snapshot of what this ticket deletes. M1 was V1-era work (PRD-M1, superseded), so it is contained in `v1-final` and needs no separate tag.
- **`infrastructure/onlyoffice/` no longer exists.** There is nothing to delete there.
- `V2-41` is `done`, so a real `FAILED` document can now be produced through the stack. V2-33 left this open, and UC-12's failure path (§2.1) now has to be shown on a real document.

## 2. Acceptance criteria

### 2.0 Preconditions (already satisfied, verify only)
| Precondition | State | Evidence |
|---|---|---|
| Dependencies `V2-14`, `V2-15`, `V2-16`, `V2-26`, `V2-31`, `V2-32`, `V2-33` are `done` | Satisfied | PLAN §3 status table; V2-33 accepted on 2026-11-16 |
| `V2-39`, `V2-41` `done` (not dependencies; affect UC-01 reload and UC-12 failure evidence) | Satisfied | PLAN §3 |
| Tag `v1-final` exists and is pushed | Satisfied (V2-38) | `git ls-remote --tags origin v1-final` → `835cf28c…`; V2-38 §Results |
| V1 paths unchanged since `v1-final` | Satisfied | `git diff --stat v1-final develop -- <§2.3 paths>` empty |
| V1 frontend removed | Satisfied (V2-38) | V2-38 criterion "V1 removal" |
| M1 milestone preserved | Satisfied by `v1-final` | M1 is V1-era; no separate commit to tag |

Re-run the two `git` checks at the start of execution and paste the output into §6.

### 2.1 Parity table
- [ ] A parity record `docs/quality/test-reports/parity-v2-17-<date>.md` (frontmatter per `project-docs`, `author: "Owner"`) with one row for **each of UC-01 to UC-12** and one for **every P0 FR**. Each row has: status `passed` / `not passed` / `deferred (recorded)`, the evidence (test class or file, test report, `docs/quality/evidence/<ticket>/` screenshot or browser run, or ticket §Results), and the implementing ticket.
  - P0 FRs = every PRD-V2 §3 FR not marked P1: FR-01–FR-04, FR-06–FR-23, FR-25–FR-31. FR-05 and FR-24 are P1 and are listed separately.
  - **UC-03 / FR-05 (domain join, P1) and FR-24 (CSV import, P1) are not implemented.** TECH-V2-core-api §16 records them as **Deferred**, and `InvitationController` says FR-24 is deferred. PRD-V2 §7 nevertheless says "UC-01 to UC-12 work". The record marks them `deferred (recorded)` and the owner confirms that decision in §6. Do not implement them in this ticket.
  - UC-12 includes the failure path: one real `FAILED` file (scan or wrong format) next to `READY` files, with retry or replace (possible since V2-41).
  - Where to start for evidence (check each; the ticket list is a pointer, not proof):

    | UC | Ticket(s) |
    |---|---|
    | UC-01 first sign-in | V2-11, V2-29, V2-39, V2-15 |
    | UC-02 invite a member | V2-30, V2-33 |
    | UC-03 domain join (P1) | none: deferred |
    | UC-04 upload and ask | V2-09, V2-10, V2-12, V2-15, V2-31, V2-32 |
    | UC-05 not covered | V2-10, V2-13, V2-15 |
    | UC-06 evaluation | V2-05, V2-07, V2-37 (`eval/`) |
    | UC-07 invite with profile | V2-23, V2-30, V2-33 |
    | UC-08 departments | V2-23, V2-33 |
    | UC-09 upload + suggestions | V2-24, V2-25, V2-31, V2-33 |
    | UC-10 restricted document | V2-24, V2-26, V2-10 |
    | UC-11 revoke access | V2-23, V2-24, V2-26 |
    | UC-12 corpus load + recognized content | V2-19, V2-20, V2-31, V2-32, V2-41 |

### 2.2 Safety checks before removal (record the command and result of each in §6)
- [ ] **No V1 references left in V2 code.** Run, on the working branch:
  `git grep -n -i -E "auth-service|user-service|knowledge-service|metadata-service|feedback-service|api-gateway|ai-qa-service|ingestion-service|init-db|combined_init|onlyoffice|seed_unanswered|docker-compose\.dev|:3001\b|poliwise" -- services/core-api services/ai-service frontend/web eval tests scripts .github/workflows docker-compose.v2.yml infrastructure/db infrastructure/storage infrastructure/modal`
  The baseline on 2026-11-16 is listed below. After §2.4–§2.7 it must be empty except for the allowed provenance comments.
  - Allowed (port provenance, resolvable through `v1-final`): `services/core-api/.../identity/GoogleIdTokenVerifier.java:34` ("Ported from V1 `auth-service`"), `infrastructure/db/README.md:3` (the "never touches the legacy stack" sentence: reword it to past tense, or keep it as provenance).
  - Must go: `.github/workflows/ci.yml` (3 matrix lines), `tests/integration/google-auth-flow.mjs`, `scripts/check-services.ps1`, `check-conventions.ps1`, `run-tests.ps1`, `validate-build.ps1`, `trace-request.ps1`, `test-google-auth.ps1`, `e2e-upload-dedup-test.ps1`, `fast_ingest.py`, `fast_ingest_stream.py`.
  - `frontend/web`, `eval/`, `services/ai-service`, `docker-compose.v2.yml`: 0 hits already.
- [ ] **No dangling Markdown links.** `./scripts/docs/check-docs.ps1` (strict) passes after the deletion. Strict mode also checks links in `docs/archive/`. Known links into deleted paths (2026-11-16): `docs/portfolio/implementation-evidence.md` (26 links into V1 services), `docs/research/audit-retrieval-stack-research-2026-10-18.md:43`, and `README.md:129` (into `v1-frozen.md`). Rewrite them as permalinks pinned to the tag (`https://github.com/N-Tien-L/SOPilot/blob/v1-final/<path>`) or as plain code text. Do not delete the content.
- [ ] **Ported parts have V2 tests, green without V1** (ADR-004 §4.5). Record each in §6:

  | ADR-004 §4.5 part | V2 location | Tests |
  |---|---|---|
  | Google token verification, `(issuer, sub)` binding | `core-api` `identity/GoogleIdTokenVerifier` (V2-11; port source recorded in V2-11) | `GoogleIdTokenVerifierTest` |
  | Refresh-token rotation | `core-api` `identity/RefreshTokenService` (V2-29, V2-39) | `SessionWorkspaceIT` |
  | Extraction, chunking, embedding | `ai-service` (rewritten, not ported: TECH-V2-ai-service, V2-09/V2-20/V2-22) | `test_pdf.py`, `test_markdown.py`, `test_chunk.py`, `test_ingest_units.py`, `test_ingest_worker.py` |
  | Hybrid retrieval SQL | `ai-service` `sopilot_ai.retrieval` (rewritten, V2-09) | `test_retrieval_units.py`, `integration/test_retrieval.py` |
  | Frontend chat components | not ported: deleted in V2-38, rebuilt in V2-15 | `frontend/web` Vitest |
- [ ] **CI is green with V2 only.** `ci.yml` after §2.5 and `tenant-isolation.yml` pass on the branch's PR, and `eval/` passes (`cd eval; uv sync --extra dev; uv run pytest -q`).
- [ ] **Clean V2 bring-up starts no V1 container.** Bring the stack up from empty volumes with the renamed `docker-compose.yml` under a **throwaway project name**: `docker compose -p sopilot-parity up -d --build`. The owner's `sopilot-v2` project and its volumes are never used for this. Stop the owner's stack first with `down` (no `-v`), or override the `V2_*_PORT` variables. Run the V2-16 demo (`scripts/seed-demo.ps1`) and the UCs from §2.1. Confirm `docker ps` shows only `sopilot-parity-*` containers. Removing the throwaway project's volumes afterwards (`down -v` on `-p sopilot-parity` only) needs the owner's approval at the prompt (CLAUDE.md constraint 3).

### 2.3 Removal (separate commit; explicit paths only, never a recursive wildcard)
- [ ] Delete these tracked paths (file counts on 2026-11-16):

  | Path | Tracked files |
  |---|---:|
  | `services/auth-service/` | 112 |
  | `services/user-service/` | 89 |
  | `services/knowledge-service/` | 100 |
  | `services/metadata-service/` | 80 |
  | `services/feedback-service/` | 104 |
  | `services/api-gateway/` | 67 |
  | `services/ai-qa-service/` | 77 |
  | `services/ingestion-service/` | 70 |
  | `infrastructure/init-db/` (incl. `reset-and-bootstrap.ps1`) | 17 |
  | `infrastructure/combined_init.sql` | 1 |
  | `infrastructure/seed_unanswered_questions.sql` (V1 seed, not used by V2-16) | 1 |
  | `docker-compose.yml` (V1), `docker-compose.dev.yml` | 2 |
  | `tests/integration/google-auth-flow.mjs`, `scripts/test-google-auth.ps1` (V1 auth flow) | 2 |
  | `scripts/e2e-upload-dedup-test.ps1` (V1 gateway `:3001`, ingestion `:8088`) | 1 |
  | `scripts/fast_ingest.py`, `scripts/fast_ingest_stream.py`, `scripts/convert_sql_to_csv.py` (V1 `poliwise-postgres` seed loaders) | 3 |
  | `.claude/rules/v1-frozen.md` | 1 |

  Use `git rm -r -- <exact path>` per row, so only tracked files are removed.
- [ ] `infrastructure/onlyoffice/` is already absent; record this in §6 and skip it.
- [ ] **Untracked local files are not deleted by this ticket:** `infrastructure/seed/seed_data.sql` (gitignored V1 data dump), `config/rabbitmq.env`, and anything ignored inside the V1 service folders (`.env`, `node_modules`, `target`, `.venv`). After `git rm`, list what is left in those folders (`git status --ignored -- services/<name>`) and give the owner the list. The owner deletes them. The `.gitignore` lines for `infrastructure/init-db/010_seed_data.sql` and `infrastructure/seed/seed_data.sql` stay until the owner has removed the local files.
- [ ] **Docker volumes are not deleted.** Record the cleanup commands for the owner in §6 only: the V1 project is `sopilot` (folder name, no `name:`), with volumes `sopilot_postgres_data`, `sopilot_rabbitmq_data`, `sopilot_minio_data`, `sopilot_redis_data`. Check them with `docker volume ls --filter name=sopilot_` and remove them with `docker volume rm <name>` when the owner chooses. The V2 volumes (`sopilot-v2_*`) are untouched.

### 2.4 Compose rename (same change set, own commit before the removal)
- [ ] `git mv docker-compose.v2.yml docker-compose.yml` **after** the V1 `docker-compose.yml` is removed. Keep `name: sopilot-v2` so the owner's existing volumes still match, and update the header comment (no "legacy stack" or `-f docker-compose.v2.yml`).
- [ ] Update every reference to `docker-compose.v2.yml`, written as `docker compose ...` without `-f` (or `-f docker-compose.yml`). The list, outside archived docs and done tickets, is:
  - Code/tests: `eval/sopilot_eval/infra_check.py` (lines 145, 222, which read the file), `eval/tests/test_harness_regressions.py:142`, and comments in `services/core-api/src/test/java/com/sopilot/core/support/V2Postgres.java:15` and `tests/tenant-isolation/conftest.py:3`.
  - Scripts: `scripts/pre-commit-check.ps1` (step 4 becomes a single `docker compose -f docker-compose.yml --env-file .env.example config --quiet`), plus the help text of `scripts/seed-demo.ps1`, `scripts/measure-ttft.ps1` and `scripts/measure-ingest-latency.ps1`.
  - `.env.example` (comments on lines 4, 41, 51).
  - `.claude/settings.json` allow list (the 4 `docker compose -f docker-compose.v2.yml …` entries), `.claude/hooks/test_guard.py` (command strings; behaviour must not change), `.claude/skills/debug-and-diagnose/SKILL.md`, `.claude/skills/flyway-migration/SKILL.md`.
  - Docs: `CLAUDE.md`, `README.md`, `frontend/web/README.md`, `services/core-api/README.md`, `infrastructure/db/README.md`, `docs/architecture/system-overview.md`, `docs/architecture/decisions/adr-010-frontend-stack.md` (add a dated note, do not rewrite), `docs/operations/local-development.md`, `docs/operations/troubleshooting.md`, `docs/quality/quality-gates.md`, `docs/portfolio/implementation-evidence.md`.
  - Done tickets (`V2-08`, `V2-12`, `V2-15`, `V2-16`, `V2-32`, `V2-36`, `V2-38`) and archived docs are history: leave them.

### 2.5 CI (`.github/workflows/ci.yml`)
- [ ] Delete the jobs `backend-java` (matrix `auth-service, feedback-service, knowledge-service, metadata-service, user-service`, JDK 17) and `backend-python` (matrix `ai-qa-service, ingestion-service`), together with their "V1 (frozen)" comment.
- [ ] `frontend-and-gateway`: drop `services/api-gateway` from the matrix. Rename the job to `frontend` without a matrix (`working-directory: frontend/web`), and keep `pnpm install --frozen-lockfile`, `pnpm build`, `pnpm lint` and `pnpm test`. The frontend job must not disappear.
- [ ] Keep `secret-scan`, `migrations`, `docs`, `guard-selftest`, `core-api-unit` and `ai-service-unit` unchanged. `tenant-isolation.yml` has no V1 reference and needs no change.

### 2.6 Scripts (2-service V2 stack)
- [ ] `scripts/run-tests.ps1`: `ValidateSet` = `core-api`, `ai-service`, `frontend`. Remove the V1 Java names from the `core-api` case, and remove the `ai-qa-service`/`ingestion-service` and `api-gateway` cases.
- [ ] `scripts/validate-build.ps1`: scopes `core`, `ai`, `web` only. Remove `$springBootScopes` and `gateway`, and make `ai` map to `services\ai-service` explicitly instead of through `"$Scope-service"`. Unknown scopes throw.
- [ ] `scripts/check-conventions.ps1`: remove the `gateway` branch. Scopes `core` → `services\core-api`, `ai` → `services\ai-service`, `web` → `frontend\web`, plus `infra` as today. Map the other CLAUDE.md scopes (`eval`, `tenant`, `ci`, `plan`) to their directories, or skip the directory check for them, but not through `services\<scope>-service`.
- [ ] `scripts/check-services.ps1`: probe `core-api` `http://localhost:8080/actuator/health`, `ai-service` `http://localhost:8000/health`, `web` `http://localhost:3000/`, and TCP Postgres `55432` and MinIO `59000`. Honour `V2_CORE_API_PORT`, `V2_AI_SERVICE_PORT`, `V2_WEB_PORT`, `V2_POSTGRES_PORT` and `V2_MINIO_API_PORT` when set. Remove RabbitMQ, Redis and the V1 ports. **Exit 1 if any check is red**: today the script always exits 0, so "passes" means nothing. `ai-worker` has no HTTP port; check it with `docker compose ps ai-worker` when it runs in compose, or report it as "not checked" when run from source.
- [ ] `scripts/trace-request.ps1`: rewrite for the V2 route map from `frontend/web/proxy.ts`: `/api/v1/**` → core-api `:8080`, `/ai/v1/**` → ai-service `:8000`, through the web proxy `:3000`. Remove the gateway and the 8-service table.
- [ ] `scripts/pre-commit-check.ps1`: step 4 as in §2.4. Step 3 maps `services/<name>/` to `run-tests.ps1` scopes; after removal only `core-api` and `ai-service` can appear. Fix the stale comment saying "the frontend has no test script yet".
- [ ] `tests/smoke/smoke-check.ps1` is kept: it wraps the new `check-services.ps1` and now probes V2. `tests/README.md` lists it as V2, removes the `integration/google-auth-flow.mjs` row and the "two V1 entries" sentence, and stops pointing at `v1-frozen.md`.
- [ ] Not touched (already V2 or neutral): `check-env.ps1`, `check-migrations.ps1`, `llm-env.ps1`, `seed-demo.ps1` (only the compose name in its help), `measure-*.ps1` (same), `scripts/docs/*`, `scripts/diagrams/*`. `check_llm_providers.py` is a V2-02 Groq/Gemini artifact: leave it, it does not depend on V1.

### 2.7 Guidance (`CLAUDE.md`, `.claude/`, `README.md`)
- [ ] `CLAUDE.md` (stay under 120 lines):
  - §Project: replace the "V2 is the product … frozen … V2-17 deletes it" bullet with a one-line note that V1 was removed in V2-17 and is preserved at tag `v1-final`. Rephrase the *Poliwise* note (the codename now survives only in history).
  - §Architecture: frontend row: drop "still V1-wired until V2-15".
  - §Commands and the compose paragraph: `docker compose up -d postgres flyway-core flyway-rag minio minio-init` (no `-f docker-compose.v2.yml`); CI description without "frozen V1 jobs", plus the `frontend` job.
  - Constraint 3: drop the `reset-and-bootstrap.ps1` clause (the script is deleted). Constraint 8: drop "V1 paths".
  - §Known drift: keep the Modal item (still valid); add nothing V1.
- [ ] `.claude/settings.json` (prompts before the edit): remove the 8 `Edit(./services/<v1>/**)` entries and `Edit(./infrastructure/init-db/**)`. Keep `Edit(./docker-compose.yml)`, which now guards the V2 file, and remove `Edit(./docker-compose.v2.yml)`. Update the 4 compose allow entries (§2.4). Keep the `*reset-and-bootstrap*` ask entries, which are harmless; if you remove them, state why in §6. `python .claude/hooks/test_guard.py` passes.
- [ ] `.claude/agents/v2-reviewer.md:36` (prompts) and `.claude/skills/execute-ticket/SKILL.md:50`: drop "V1 paths" from the checklists.
- [ ] Delete `.claude/rules/v1-frozen.md` (§2.3). Its "Known V1 drift" list exists only there, and `README.md:129` links to it. Either link the README to the tag permalink of the rule, or drop the sentence.
- [ ] `README.md`: rewrite the V1 parts (lines 12, 35–40 Mermaid of the V1 services, 94 "web image still wired to the V1 gateway", 122 "V1 legacy stack" command, 129 drift link) into a short history paragraph pointing at `v1-final`. Keep the V1 audit findings as the motivation for V2.

### 2.8 Architecture and quality docs
- [ ] `docs/architecture/system-overview.md:19`: implementation status without "frontend still V1-wired until V2-15", and the compose name updated.
- [ ] `docs/operations/local-development.md:64`: the `web` image runs the V2 screens (not "an empty home; the real screens arrive with V2-15"), and the compose name updated. Same for `troubleshooting.md`.
- [ ] `docs/quality/quality-gates.md` (lines 31–32, 47) and `docs/quality/testing-strategy.md` (lines 38, 62): remove the frozen V1 jobs and tests, and add the `frontend` CI job.
- [ ] `docs/architecture/components/core-api.md:38`, `:217` and `ai-service.md:43`: provenance mentions of V1 services are allowed. Add "(preserved at tag `v1-final`)" where a reader would look for the old file.
- [ ] `docs/architecture/domain/identity-and-access.md:20` ("V1 roster admission does not apply"): keep it as provenance, or drop it.
- [ ] ADR-001, ADR-002, ADR-003, ADR-004 §4.4/§4.5, ADR-005, ADR-007 and ADR-010 describe V1 as decision history. **Do not rewrite them** (CLAUDE.md constraint 11: ids and sections are cited). ADR-004 §4.5's last bullet is fulfilled by this ticket; add one dated note there.
- [ ] `docs/portfolio/engineering-case-study.md` (the V1 audit narrative) stays. `docs/portfolio/implementation-evidence.md` §"Capability inventory: V1 (frozen)" keeps its content, with its links rewritten (§2.2).
- [ ] `docs/architecture/api/`, `data/` and `components/frontend.md` had no V1 references on 2026-11-16. Re-check them with the §2.2 grep and record "no change".

### 2.9 Gate
- [ ] `./scripts/pre-commit-check.ps1` PASS on the final tree.
- [ ] `./scripts/check-services.ps1` exits 0 with only the 2-service V2 stack running (core-api, ai-service, worker, web, Postgres, MinIO), and exits 1 with core-api stopped (negative check).
- [ ] `./scripts/docs/check-docs.ps1` PASS, `uv run --no-project --with pyyaml python eval/sopilot_eval/plan_check.py` PASS, `./scripts/check-migrations.ps1` PASS, `python .claude/hooks/test_guard.py` PASS.
- [ ] `./scripts/validate-build.ps1 -Scope core|ai|web` and `./scripts/run-tests.ps1 -Scope core-api -Type unit`, `-Scope ai-service -Type unit` and `-Scope frontend` PASS. `-Scope auth-service` (any V1 name) is rejected by `ValidateSet`.
- [ ] The §2.2 grep is empty apart from the allowed provenance lines, and it also has no hits in `.claude/`, `CLAUDE.md` or `README.md` apart from history wording.
- [ ] No commit without an explicit owner request (CLAUDE.md constraint 9).

## 3. Changed files
| Path | Action |
|---|---|
| `docs/quality/test-reports/parity-v2-17-<date>.md` | CREATE (parity record, §2.1) |
| The 8 V1 service folders, `infrastructure/init-db/`, `infrastructure/combined_init.sql`, `infrastructure/seed_unanswered_questions.sql`, `docker-compose.dev.yml`, V1 `docker-compose.yml` | DELETE (§2.3) |
| `tests/integration/google-auth-flow.mjs`, `scripts/test-google-auth.ps1`, `scripts/e2e-upload-dedup-test.ps1`, `scripts/fast_ingest.py`, `scripts/fast_ingest_stream.py`, `scripts/convert_sql_to_csv.py` | DELETE |
| `.claude/rules/v1-frozen.md` | DELETE |
| `docker-compose.v2.yml` → `docker-compose.yml` | RENAME (§2.4) |
| `.github/workflows/ci.yml` | MODIFY (§2.5) |
| `scripts/run-tests.ps1`, `validate-build.ps1`, `check-conventions.ps1`, `check-services.ps1`, `trace-request.ps1`, `pre-commit-check.ps1`, `seed-demo.ps1`, `measure-ttft.ps1`, `measure-ingest-latency.ps1` | MODIFY (§2.6, §2.4) |
| `eval/sopilot_eval/infra_check.py`, `eval/tests/test_harness_regressions.py` | MODIFY (compose name) |
| `services/core-api/src/test/java/com/sopilot/core/support/V2Postgres.java`, `tests/tenant-isolation/conftest.py` | MODIFY (comment only) |
| `.env.example` | MODIFY (comments) |
| `CLAUDE.md`, `README.md`, `tests/README.md`, `frontend/web/README.md`, `services/core-api/README.md`, `infrastructure/db/README.md` | MODIFY (§2.7) |
| `.claude/settings.json`, `.claude/hooks/test_guard.py`, `.claude/agents/v2-reviewer.md`, `.claude/skills/{debug-and-diagnose,flyway-migration,execute-ticket}/SKILL.md` | MODIFY (prompts before edit) |
| `docs/architecture/system-overview.md`, `components/core-api.md`, `components/ai-service.md`, `decisions/adr-004-two-service-architecture.md` (dated note), `decisions/adr-010-frontend-stack.md` (dated note) | MODIFY (§2.8) |
| `docs/operations/local-development.md`, `docs/operations/troubleshooting.md`, `docs/quality/quality-gates.md`, `docs/quality/testing-strategy.md` | MODIFY |
| `docs/portfolio/implementation-evidence.md`, `docs/research/audit-retrieval-stack-research-2026-10-18.md` | MODIFY (links to `v1-final` permalinks) |
| `docs/execution/initiatives/v2-sopilot-mvp/PLAN.md`, this ticket | MODIFY (status, evidence) |

## 4. Guide
1. **Branch.** Create `chore/infra-remove-legacy` from an up-to-date `develop`. Check `git status` first, and leave the owner's untracked files alone.
2. **Verify the preconditions** (§2.0) and paste the output into §6.
3. **Parity.** Write the parity record (§2.1). If the stack is needed, use the throwaway `-p sopilot-parity` project (§2.2). If a P0 row is `not passed`, stop and ask the owner. Removal waits until every P0 row is `passed` and the P1 rows are confirmed `deferred`.
4. **Safety checks** (§2.2): run them and record each result.
5. **Commit A, references** (`chore(infra): point scripts, CI and docs at the V2-only stack (V2-17)`): §2.5, §2.6, §2.7 (except deleting `v1-frozen.md`), §2.8, link rewrites. Every check except the "no V1 paths exist" ones can already pass here, while V1 still exists.
6. **Commit B, removal** (`chore(infra): remove the V1 services and infrastructure (V2-17)`): only the `git rm` of §2.3, including `v1-frozen.md`, so the deletion stays reviewable on its own.
7. **Commit C, rename** (`chore(infra): rename docker-compose.v2.yml to docker-compose.yml (V2-17)`): the `git mv` plus the reference updates from §2.4. Then run the clean bring-up from §2.2 on the renamed file.
8. **Gate** (§2.9), a `v2-reviewer` pass over the full diff, then the docs (`project-docs`): this ticket's §6, PLAN status `review` with evidence. Owner review moves it to `done`.
9. Commit and push only when the owner asks. Compose, `.github/workflows/**`, `.claude/settings.json`, `.claude/hooks/**` and `v2-reviewer.md` edits prompt for approval; expect that.

## 5. Testing
`./scripts/pre-commit-check.ps1`, `./scripts/check-services.ps1` (2-service stack, with a positive and a negative run), `./scripts/docs/check-docs.ps1`, `plan_check.py`, `./scripts/check-migrations.ps1`, `python .claude/hooks/test_guard.py`, `./scripts/validate-build.ps1 -Scope core|ai|web`, `./scripts/run-tests.ps1 -Scope core-api|ai-service|frontend -Type unit`, `cd eval; uv run pytest -q`, `cd tests/tenant-isolation; uv run pytest -v` (Docker), and CI on the PR (`ci.yml` + `tenant-isolation.yml`). Browser: the UC rows of the parity record that need the UI are run in a browser on the throwaway stack; say which ones.

## 6. Results
**Status 2026-11-17: parity passed; removal in progress.** The parity record [TEST-REPORT-001](../../../../quality/test-reports/parity-v2-17-2026-11-16.md) has verdict **PASSED_WITH_WARNINGS**. The first run (2026-11-16) failed UC-04 and FR-11 (reasoning streamed as answer text, Finding F1; cause `_pump` in `services/ai-service/src/sopilot_ai/conversations/steps.py:136`). The owner chose a separate fix, [`V2-42`](V2-42-ai-service-reasoning-leaks-into-answer.md), committed as `88c66ef`, merged into `develop` locally (`25e83cb`), and merged into this branch (`9809f5e`; a rebase was not possible because the working tree holds the owner's uncommitted edits to `CLAUDE.md` and two skills, which were left alone). The full throwaway-stack run then passed on this branch (record, "Re-run on the merged branch").

**Preconditions (§2.0), run on `develop` (345f1c8)**
- `git ls-remote --tags origin v1-final` → `835cf28c1bedbcbb89cdd20d0cf4cbe73f93d8b6 refs/tags/v1-final`.
- `v1-final` is an ancestor of `develop` (345f1c8).
- `git diff --stat v1-final develop -- <§2.3 paths>` → empty.
- `662eac2..345f1c8` = 10 V2-40 commits, none touches a V1 path.

**Safety checks (§2.2)**
- Grep baseline: 52 hits in 13 files, equal to the list in the ticket.
- Not run yet (removal has not started): grep after removal, `check-docs` after removal, CI on the PR.
- Ported parts (ADR-004 §4.5), run in this work: `GoogleIdTokenVerifierTest` 18/18; `SessionWorkspaceIT` 30/30; ai-service `test_pdf`, `test_markdown`, `test_chunk`, `test_ingest_units`, `test_ingest_worker`, `test_retrieval_units` and integration `test_retrieval` "122 passed".
- Suites: core-api `mvnw verify` unit "Tests run: 126, Failures: 0", IT "Tests run: 261, Failures: 0", BUILD SUCCESS; ai-service `run-tests -Type all` "766 passed, 15 xfailed"; frontend `pnpm test` "206 passed (15 files)"; eval `uv run pytest -q` "157 passed"; `tests/tenant-isolation` "31 passed".

**Bring-up on a throwaway project (`-p sopilot-parity`)**
- `docker-compose.v2.yml` hard-codes `container_name` and `networks.sopilot-v2.name`, so `-p sopilot-parity` alone collides with the owner's stack. Workaround: a scratch override file (`container_name: !reset null` on all 9 services, network renamed `sopilot-parity-network`), ports 15432/19000/19001/18080/18000/13000, `SOPILOT_FRONTEND_ORIGIN=http://localhost:13000`, `RERANK_ENABLED=false` for the first run (the owner's `SOPILOT_RERANK_BASE_URL` used the `sopilot-vllm-serve` label and returned 404; the `sopilot-vllm-rerank` URL returns 200 and was used, with rerank on, for the V2-42 re-run). The override file is not in the repo.
- `docker ps` showed only `sopilot-parity-*` containers from the project and 0 V1 containers. Unrelated `github-mcp-server` containers were also running; the owner accepted the scoped check.
- Environment findings: the Docker VM had 5 GB, so the worker was OOM-killed (raised to 10 GB in `.wslconfig`); `ai-worker` has no restart policy; a stalled Hugging Face Hub download hung the first question (pings only, nothing logged) until the container was restarted.

**Owner decisions (2026-11-16)**
- UC-03, FR-05 and FR-24 are `deferred (recorded)` (TECH-V2-core-api §16).
- F1 is fixed in a separate ticket, `V2-42`.
- F3: keep the code; `docs/architecture/components/core-api.md:501` now says `LOGIN` is recorded in the user's personal workspace (corrected on this branch).
- FR-13: the reasoning stays visible in the "Thought for N s" block; paraphrased rules inside it are accepted, no extra guard.

**Pending**
- Browser checks of the parity rows, if the owner wants them (none was run in V2-17).
- `check-docs` after removal, CI green on the PR, the §2.9 gate, `v2-reviewer` pass.
- The §2.2 clean bring-up is repeated on the renamed `docker-compose.yml` after Commit C. The 2026-11-16 throwaway project was removed with the owner's approval (`down -v` on `-p sopilot-parity`: volumes `sopilot-parity_postgres_data`, `sopilot-parity_minio_data` and network `sopilot-parity-network`); the owner's `sopilot-v2_*` and the V1 `sopilot_*` volumes were not touched.
- Not yet recorded because removal has not started: removed-path list, leftover untracked files, V1 volume cleanup commands.
