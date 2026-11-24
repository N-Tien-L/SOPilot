---
id: TEST-PLAN-001
title: "End-to-end test plan: business flows, access rules and screens as real people use them"
status: draft
created: 2026-11-21
updated: 2026-11-21
author: "Owner"
---

# End-to-end test plan

What this plan proves that the unit and integration suites do not: the whole product, driven the way people use it (browser and HTTP, real logins, real roles), behaves correctly in its business rules, its access rules and its screens. It sits above the layers in the [testing strategy](../testing-strategy.md) and gates nothing in CI yet (it needs the full local stack).

## 1. How it runs

| | |
|---|---|
| Stack | The local stack that is already up: infrastructure in compose, core-api, ai-service, ai-worker and the web app. Setup: [local development](../../operations/local-development.md). |
| Runner | Playwright in [`tests/e2e`](../../../tests/e2e/) (its own `pnpm` project). `./scripts/run-e2e.ps1` checks the stack, runs the suite and prints the counts. |
| Data | Each run builds one throwaway TEAM workspace through the API and deletes it at the end. The owner's real workspaces and the research corpus are never touched. `-Keep` keeps it for a look (`pnpm --dir tests/e2e cleanup` removes it). |
| Logins | Dev login (`local` profile only). One account per persona, so no Google account is needed. |
| Time | About 3 to 6 minutes, most of it waiting for one document to reach `READY` (`05-ingest-ready`). |
| Safety | The suite never starts or stops containers and never deletes volumes. A run that must not touch a persistent database should use a stack of its own. |

## 2. Personas (built by `tests/e2e/global-setup.ts`)

| Key | Role | Department | Publisher of | Why it exists |
|---|---|---|---|---|
| `owner` | OWNER | none | nothing (the workspace publisher role is moved to `wsPub`) | An owner who is not a publisher: assigns, revokes, never writes content |
| `admin` | ADMIN | none | nothing | Manages people and catalogs, no document rights |
| `wsPub` | MEMBER | none | the whole workspace | Publishes company-wide documents |
| `alphaPub` | MEMBER | Alpha | Alpha | Department publisher: manages Alpha documents only |
| `alphaMember` | MEMBER | Alpha | nothing | Reads what Alpha may read |
| `betaMember` | MEMBER | Beta | nothing | Another department: must not see Alpha documents |
| `loner` | MEMBER | none | nothing | No department: reads workspace documents only |
| `spareA`, `spareB` | MEMBER | none | nothing | Moved between departments by the specs, so nobody else is disturbed |

Documents: `E2E Company Policy` (visibility `WORKSPACE`, prepared by "HR office", published by `wsPub`) and `E2E Alpha SOP` (visibility `DEPARTMENTS`: Alpha, published by `alphaPub`).

## 3. Scenarios

"Spec" is the automated check; the charter in section 4 covers what only a person or a browser agent can judge.

| # | Business rule or flow | Expected | Spec |
|---|---|---|---|
| A1 | Department document reach | Read by Alpha, the owner and the admin; not by Beta, a person without department, or the workspace publisher | `01` |
| A2 | Direct link outside the reader scope | Detail and download are `404`, never `403` (nothing is revealed) | `01` |
| A3 | Workspace document reach | Everyone reads it | `01` |
| A4 | Department filter on the list | `403` for anyone outside that department who is not an owner or admin; works for the others | `01` |
| A5 | Visibility filter | Separates workspace from department documents; an unknown value is `400` | `01` |
| P1 | Who may publish | A department publisher cannot publish for the whole workspace, nor the workspace publisher for a department (`403 NOT_PUBLISHER`) | `01` |
| P2 | Who may edit | Only the responsible publisher; a reader is `403`, an outsider `404`, the owner `403` | `01` |
| P3 | Moving ownership | Not by a publisher | `01` |
| B1 | "Prepared by" | A department document defaults to the department name; a workspace document keeps what was typed; the publisher can change and clear it; over 100 characters is refused | `01`, `03` |
| M1 | Member names | A member name is the account name, because the invitation carries none | `01`, `02` |
| M2 | Plain member and admin limits | A member cannot list people, read the audit log or assign publishers; an admin cannot assign publishers | `01`, `02` |
| U1 | Members screen | Tabs Members and Invitations only; search; Role, Status and Department filters that can return to "All" | `02` |
| U2 | Bulk move | Several people moved to a department at once and back | `02` |
| U3 | Invitation | Department select present, no separate full-name field, link shown once, pending row shows the department | `02` |
| U4 | Departments screen | One list with publishers; create with several people picked by search and a publisher among them; the people really move; an admin cannot change publishers; a member is told it is for owners and admins | `02` |
| D1 | Documents tabs by role | Member: one read-only list. Department publisher: Manage for the department and All documents (read-only). Workspace publisher: Manage only. Owner: Manage and Categories with the department filter. Admin: read plus Categories | `03` |
| D2 | Upload as a department publisher | Scope shown as "Alpha only", no picker; "Prepared by" defaults to Alpha; the row shows the preparer and the publisher; another department never sees it | `03` |
| D3 | Edit saves | The details save with no tag, and "Prepared by" changes | `03` |
| D4 | Filters | Every filter returns to All; no tag filter; a new category becomes a filter | `03` |
| H1 | Page health | No script error, no HTTP 5xx, no horizontal overflow on a desktop and a phone width, for four personas across every screen | `04` |
| I1 | Ingestion | Both documents reach `READY` and are answerable | `05` |
| R1 | Processing report | A reader gets the family, rules and chunk layout without chunk text; a clicked chunk carries its text; outside the reader scope it is `404`, never `403` | `06` |

## 4. Charter for a browser agent (exploratory, after the suite)

A person or an agent opens the kept workspace (`./scripts/run-e2e.ps1 -Keep`, personas in `tests/e2e/.world.json`) and tries to break what the scripts cannot judge. Sign in as a persona with `POST /api/v1/auth/dev-login` then `POST /api/v1/auth/switch-workspace` through the web origin, or with the dev-login form on `/login`.

1. **Readability and layout.** For each persona and each screen at 1280 and 390 pixels: text clipped, overlapping, unreadable contrast, controls that look disabled but are not, empty states that say nothing useful.
2. **Wording.** Every message names what happened and what to do next; no raw codes; "publisher", "owner", "prepared by" mean the same everywhere.
3. **Keyboard.** Every dialog opens with focus inside, closes with Escape, and returns focus; tabs move with the arrow keys; selects are operable.
4. **Errors.** Stop the ai-service container or use an expired session and look at what each screen says; the app must not show a blank page.
5. **Chat (needs the LLM provider, which may cost money).** Ask a question whose answer is in `E2E Alpha SOP` as `alphaMember` (answers with a citation) and as `betaMember` (must not cite it). If the provider is not configured, record chat as not checked.
6. **Anything a real user would try that this plan does not name.** Record it as a new scenario.

## 5. Evidence and report

- Save screenshots and the Playwright report under `artifacts/testing/` (gitignored); do not commit binaries.
- Write the result as a test report in [`docs/quality/test-reports/`](../test-reports/) with: date and commit, stack state (which services were up, which image was current), the suite counts, every failure with its cause (app bug or test bug), the exploratory findings, and **what was not checked** (chat, other browsers, other widths, Docker-only suites).
- A failing check is an app bug or a test bug. Stop after three attempts to repair a test and report the cause. An unattended run reports app bugs; it does not change application code.

## 6. Known gaps

- Chat answers and citations are not in the automated suite (they need the LLM provider). Retrieval isolation is covered by the ai-service integration tests and `tenant-isolation.yml`.
- Only Chromium. Safari does not keep the sign-in cookie on plain `http://localhost` (see local development).
- Not in CI: the suite needs the whole stack and a writable database.
- The approval step for new documents (draft until a publisher approves) and the upload review step are designed but not built; scenarios for them are added with their tickets.
