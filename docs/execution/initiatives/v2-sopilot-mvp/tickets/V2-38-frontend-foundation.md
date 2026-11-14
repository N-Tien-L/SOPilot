---
id: V2-38
title: "Frontend foundation: API client, session, SSE client, TanStack Query, Vitest, V1 removal"
type: refactor
status: review
created: 2026-11-14
updated: 2026-11-14
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-11, V2-29]
blocks: [V2-15]
branch: "refactor/web-v2-foundation"
assignee: pair
refs:
  - docs/architecture/decisions/adr-010-frontend-stack.md
  - docs/architecture/components/frontend-nfrs.md
  - docs/architecture/components/frontend-feature-inventory.md
---

# TICKET V2-38: Frontend foundation

> **Scope:** `web` | **Size:** `L` | **Priority:** `P0`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `refactor/web-v2-foundation`

## 1. Context & goal
Implements [ADR-010](../../../../architecture/decisions/adr-010-frontend-stack.md): keep Next.js 16 as a client-rendered app and replace the V1 foundation (client, tokens, i18n, dead features) before any V2 screen is built. Requirement ids `C#`, `S#`, `R#`, `M#` are from [frontend-nfrs](../../../../architecture/components/frontend-nfrs.md). Screens and the visual direction are **not** in this ticket: they belong to V2-15, V2-31, V2-32 and V2-33.

## 2. Acceptance criteria
- [x] **Tag first.** Create the tag `v1-final` on `develop` before this branch merges (it is the last commit whose frontend runs against the old stack; V2-17 reuses the tag).
- [x] **Proxy.** `/api/v1/**` goes to core-api and `/ai/v1/**` to ai-service through a `proxy.ts` rewrite that reads `CORE_API_URL` and `AI_SERVICE_URL` at run time, with `compress: false` and `experimental.proxyClientMaxBodySize` above core-api's 20 MB upload limit (the default 10 MB cuts larger multipart bodies; ADR-010 §4.3); `rewrites()` is not used. Works in compose and with `pnpm dev`; the variables are in `frontend/web/.env.example`. The `docker-compose.v2.yml` and `.github/workflows/ci.yml` edits this ticket needs prompt for approval (CLAUDE.md #8); the Dockerfile does not.
- [x] **Same origin only.** The client uses relative base URLs. `NEXT_PUBLIC_API_URL` is removed from the code (`lib/api.ts`, `services/api-client.ts`, `services/document.service.ts`), the Dockerfile, the compose build args and the README, so no request bypasses the proxy. The compose `web` service gets `CORE_API_URL` and `AI_SERVICE_URL` as run-time env (and `depends_on` ai-service). `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is a build-time value today; V2-15 decides whether to keep it build-time or expose it at run time. core-api's `SOPILOT_FRONTEND_ORIGIN` must match the web origin in both run modes.
- [x] **API client.** One `fetch`-based client with a core-api adapter (envelope, `{error:{code,message,details}}`, `traceId`) and an ai-service adapter (plain JSON, `{detail}`), typed per contract (M1, M2). `axios`, the second client and direct `fetch` calls are gone. Errors surface a fixed message and the `traceId` where present (S4, O2).
- [x] **Session.** Access token in memory only; refresh through the `HttpOnly` cookie; concurrent refreshes from several tabs merge into one request via Web Locks with a `BroadcastChannel` fallback (C5, R1). Nothing token-like in `localStorage`, `sessionStorage`, URLs or logs (S1). Workspace switch calls `POST /auth/switch-workspace`, clears all cached server state and aborts open streams (R7).
- [x] **SSE client.** `fetch` + stream reader for `POST /ai/v1/conversations/{id|new}/messages`: parses `meta`, `delta`, `replace`, `refusal`, `citations`, `done`, `error`; supports cancel; a broken or cancelled stream ends in a defined state (R4).
- [x] **Server state.** `@tanstack/react-query` v5 provider and conventions; the legacy `react-query` v3 package is removed (one data-fetching approach, M5).
- [x] **Vitest.** Runner configured with `pnpm test` (owner-approved 2026-11-14, C10). Unit tests for refresh single-flight, the SSE parser, both error adapters, and cache clearing on workspace switch. V2-31 and V2-32 add their own tests (upload queue, UTF-16 mapping) on this setup.
- [x] **V1 removal.** Delete V1 pages, components, services and stores that V2 does not use (list in ADR-010 §2.7 and the PRD §5 UI row), `lib/i18n.ts` and the language preference, and the dependencies only they use (`recharts`, `mammoth`, `sass`, `rehype-raw`, `axios`). Chat message rendering no longer uses `rehype-raw` (S2). A minimal shell stays: sign-in (dev login in `local`), a workspace-aware empty home, sign-out.
- [ ] **Gates.** `pnpm build`, `pnpm lint` (zero errors: this ticket owns clearing the 61 V1 lint errors) and `pnpm test` pass. `scripts/validate-build.ps1` runs `pnpm test` for the web scope, and the CI frontend job runs `pnpm lint` and `pnpm test` as well as the build (it runs only the build today).
- [x] **Dependencies.** Every remaining dependency is kept on purpose. Decide `dompurify`, `mark.js`, `jwt-decode` and `react-hot-toast` (keep or remove, one line each in the Results section); remove the self-dependency `"web": "file:"` in `package.json`.
- [x] **Browser check** (Chrome and Firefox, against core-api and ai-service from source): dev login; storage shows no token; two tabs refreshing at once keep the session; workspace switch clears the previous workspace's data; a streamed answer reaches the page incrementally through the proxy (not in one chunk); a 15 to 20 MB PDF uploaded through the proxy reaches core-api with the same SHA-256 (no truncation). State anything not checked.
- [x] **Compose image.** Build the `web` image once (standalone `node server.js`, not `next start`) and start it with two different `CORE_API_URL` values: requests follow the run-time value, streaming stays incremental, and an upload of about 15 MB succeeds.
- [x] **Docs.** Update `docs/architecture/components/frontend.md` (§1 to §3 to the real state), `.claude/rules/frontend.md`, `frontend/web/README.md` and `.env.example`.

## 3. Guide
- Order: tag → proxy and `.env.example` → API client and session → SSE client → TanStack Query → Vitest and tests → V1 removal → docs. Run the browser check last.
- A file-by-file pass decides the keep list. The ADR's classification was made by name and location. Candidates to keep as a starting point (adapt, do not carry over unchanged): the chat components and `components/ui` primitives; V2-15 decides the styling system and primitives.
- Not in this ticket: Google sign-in UI, workspace picker, shell and navigation, chat features (V2-15); upload (V2-31); viewer (V2-32); members, departments, publishers, audit log (V2-33); visual direction (start of V2-15, `frontend-delivery`).
- Keep the `ArchitectureTest`-style rules in mind: no `console.log`, no `any`, every TODO carries a ticket id.

## 4. Testing
```powershell
./scripts/validate-build.ps1 -Scope web
cd frontend/web; pnpm test
```
Plus notes on the browser flows tried by hand.

## 5. Changed files
| Area | Action |
|---|:---:|
| `frontend/web/proxy.ts`, `next.config.ts`, `.env.example`, `Dockerfile`, `README.md` | CREATE / MODIFY |
| `docker-compose.v2.yml` (`web` env and build args), `.github/workflows/ci.yml` (frontend lint and test), `scripts/validate-build.ps1` (`pnpm test`) | MODIFY (compose and workflow edits prompt) |
| `frontend/web/lib/` (API client, session, SSE) | CREATE (replaces `lib/api.ts`, `services/*`) |
| `frontend/web/providers/` (TanStack Query) | MODIFY |
| `frontend/web/package.json`, `vitest.config.*`, `**/*.test.ts` | MODIFY / CREATE |
| V1 pages, components, `lib/i18n.ts`, unused stores and services | DELETE |
| `docs/architecture/components/frontend.md`, `.claude/rules/frontend.md` | MODIFY |

## 6. Results
Status `review`: **not committed yet** (the owner commits). Browser and real-stack checks were run headless with Playwright on 2026-11-15 (see below). Branch `refactor/web-v2-foundation`, based on `docs/plan-frontend-foundation` because ADR-010 and this ticket are not on `develop` yet.

### Commands and results
| Check | Command | Result |
|---|---|---|
| Tag | `git tag v1-final develop` | local tag at `835cf28` (develop tip); **not pushed** |
| Unit tests | `pnpm test` (Vitest 5.1.0, Node env) | 5 files, 39 tests passed: refresh single-flight (same tab, two tabs with Web Locks, fallback without locks, failure propagation), SSE parser and event decoding, `streamAnswer` end states (`done`, `error`, HTTP error, `interrupted`, `cancelled`, network down), both error adapters, proxy target resolution, workspace switch clearing cache and streams, refresh failure handling (network keeps the session, 401 ends it) |
| Lint | `pnpm lint` | exit 0, zero errors (V1 had 61) |
| Build | `pnpm build` | exit 0 (Next 16.1.6 Turbopack, routes `/`, `/login`, `ƒ Proxy`) |
| Image | `docker build` of `frontend/web` (standalone `node server.js`) | built; removed afterwards |
| Gates in scripts | `scripts/validate-build.ps1` runs `pnpm test` for scope web; CI job runs `pnpm lint` and `pnpm test` for `frontend/web` | edited; the CI change has not run on GitHub |

### Proxy and image evidence (mock backends, not core-api and ai-service)
Two Node mock servers (A and B) stood in for the backends: `/api/v1/ping` returns its name, `/api/v1/upload` returns the byte count and SHA-256 of the body, `/ai/v1/conversations/*` emits 5 SSE events 0.6 s apart.
- **Standalone server (`node .next/standalone/server.js`), one build:** started with `CORE_API_URL` = B, then A, then B: each answered with its own name (run-time target, no rebuild). `Set-Cookie: sp_refresh=...; HttpOnly; SameSite=Strict; Path=/api/v1/auth` passed through unchanged.
- **Streaming:** with `Accept-Encoding: gzip`, five events arrived 0.55 to 0.6 s apart, not in one chunk.
- **Upload:** an 18,000,000-byte body through the proxy arrived with the same SHA-256 as the local file.
- **Docker image, run twice** with `CORE_API_URL` = `http://host.docker.internal:9101` and then `:9102` (`docker run`, not `docker compose up`): requests followed the run-time value (A, then B); SSE stayed incremental (about 0.6 s apart); the 18 MB upload matched the local SHA-256.
- The proxy was re-checked on the standalone server before the reviewer-requested `proxyTimeout: 120000` and the path-confinement guard were added; those two were covered by unit tests and a clean build, not by another run of the image.

### Dependencies (decision per package)
- `dompurify` (and `@types/dompurify`): removed; only the V1 document viewer used it, and V2-32 renders Markdown without raw HTML.
- `mark.js` (and `@types/mark.js`): removed; used only by the V1 viewer. V2-32 highlights by UTF-16 offsets and may add its own approach with agreement.
- `jwt-decode`: removed; the role and workspace come from the login/refresh response, not from decoding the token.
- `react-hot-toast`: removed together with the V1 toast components; V2-15 chooses the feedback component.
- Also removed: `axios`, `recharts`, `mammoth`, `sass`, `rehype-raw`, legacy `react-query` v3, the `"web": "file:"` self-dependency. Added: `@tanstack/react-query` 5, `vitest` (both pre-approved).
- Kept on purpose: `react-markdown` and `remark-gfm` (Markdown rendering in V2-15 and V2-32), `zustand` (session view), `clsx`, `lucide-react`, `@tailwindcss/typography`.
- `sass@1.98.0` is still in `pnpm-lock.yaml` and `node_modules` only as the optional peer of `next` and `vite` that pnpm auto-installs; no code uses it and it is not a dependency of this package.

### Real-stack and browser run 2026-11-15
Stack: `docker compose -f docker-compose.v2.yml up -d --build core-api ai-service ai-worker web` (infrastructure from compose too), so the `web` image ran with its run-time `CORE_API_URL=http://core-api:8080` and `AI_SERVICE_URL=http://ai-service:8000`; `web` waited for both services to be healthy (`depends_on`). Browsers: Playwright 1.65.1 (installed only in the session scratchpad, owner-approved, not in the repo) driving headless Chromium and Firefox 159 against `http://localhost:3000` (the origin core-api accepts). Script: scratchpad `check.mjs`; output below is from two full runs (core-api's dev login in the `local` profile).

| Check | Chromium | Firefox |
|---|:---:|:---:|
| Dev login reaches the workspace-aware home | pass | pass |
| `localStorage` and `sessionStorage` hold no token (2 chars each, `{}`); `document.cookie` cannot see the refresh cookie; URL has no token | pass | pass |
| Refresh cookie `HttpOnly; SameSite=Strict; Path=/api/v1/auth` stored by the browser (it is also `Secure`; accepted on `http://localhost`) | pass | pass |
| Reload restores the session from the cookie | pass | pass |
| 3 tabs reloaded together, 5 rounds: every tab stays signed in; **1 refresh request per round** (5 requests for 15 tab loads) | pass | pass |
| `POST /api/v1/workspaces` through the proxy (cookie rotated); after reload the page shows the new workspace | pass | pass |
| No-evidence answer through the proxy: `meta` at ~10 ms, `refusal` and `done` ~200 ms later, as separate chunks; direct to ai-service (no proxy) shows the same 1.2 s gap between `meta` and `refusal` | pass | pass |
| Grounded answer from an ingested Markdown SOP (document `READY`): `meta` at ~10 ms, `delta`, `citations`, `done` when the model answers (2.0 to 2.2 s; the first run after a cold start took 109 s) | pass | pass |
| 17,825,792-byte PDF upload through the proxy: `201`; the stored `core.document_versions` row has the same `size_bytes` and the same SHA-256 as the browser computed (checked in Postgres, first 12 hex digits `b0e45cb67ace`, `dee5944dea5a`, `8d529c59d233`); uploading the same bytes again is `409 DUPLICATE_DOCUMENT` | pass | pass |
| Sign out returns to `/login`; a reload stays signed out | pass | pass |

Other results: `docker compose config --quiet` exit 0; `pnpm dev` (`next dev`) against mock backends behaves like the production server; the plan test expects 38 tickets.

**Findings from this run**
1. **Reloading a tab while its refresh is in flight can end the session (not fixed here).** In `midreload.mjs` (Chromium), a double reload 5 ms apart lost the session on trial 2 of 12: core-api had already rotated the token, the aborted response's `Set-Cookie` never reached the browser, and the next refresh presented the used token (reuse, so the whole family is revoked). The cross-tab merge cannot prevent this because only the server knows the rotation happened. It follows from strict rotation without a grace window (TECH-V2-core-api §5.1, V2-29). A fix needs a contract change in core-api (accept the immediately previous token for a few seconds) and was decided by the owner on 2026-11-15 and is tracked as [V2-39](V2-39-core-api-refresh-grace-window.md). Normal use (reload after the page settled, several tabs loading together) was not affected.
2. A grounded answer reached the page as one `delta`, not many: that is what ai-service emitted for this model, not something the proxy added (the earlier `meta` event arrived at once; there was no buffering). Per-token deltas were therefore not observed in a browser.
3. The Playwright script first reported a session loss because it reloaded tabs while their first refresh was still in flight; that is finding 1, not the multi-tab merge. After waiting for each tab's first load, 3 tabs reloading together kept the session in all 10 rounds (two browsers, five rounds each).

### Not verified
- A person using Chrome or Firefox by hand (the checks ran headless through Playwright). No screenshots or layout check were done: the shell has two near-empty screens.
- Workspace switch clearing client-side state in the UI: there is no workspace switcher or cached data yet (V2-15), so only the server side (new workspace after reload) and the unit tests cover R7.
- Per-token streaming of a long answer in a browser (finding 2).
- The `%2e%2e` path guard and `proxyTimeout` at run time in the browser (covered by unit tests and a clean build).
- The GitHub CI job.
- The upload was 17.8 MB; a 19 to 20 MB file at the 20 MB limit was not tried.

### Mismatches and notes
- **Keep list decision (file-by-file pass):** the V1 chat components (`components/chat/*`) were deleted, not kept: they depend on V1 types, i18n and `rehype-raw`, and V2-15 rebuilds chat on the new SSE client. Only `components/ui/*` primitives were kept (minus the toast components and the `sass` loading screen). V2-15 inherits this.
- The plan test `eval/tests/test_review_regressions.py::test_v2_plan_all_frontmatter_counters_dag_and_handover_match` asserts 37 tickets but the plan has 38 since V2-38 was added in the base docs commit; the plan check itself reports no counter, DAG or row problem. Not changed here (outside this ticket).
- The Dockerfile pinned pnpm 9.15.4 while `package.json` says 10.32.1; aligned to 10.32.1 with `--frozen-lockfile`.
- `docker-compose.v2.yml` and `ci.yml` were edited as the ticket requires (both prompt for approval).
- `SOPILOT_FRONTEND_ORIGIN` defaults to `http://localhost:3000` in compose, which matches the `web` port mapping.
- `frontend/web/.gitignore` ignored `.env*` including `.env.example`; added `!.env.example`.

### Review
Round 1 (Opus 5.5): 1 BLOCKER (`.env.example` ignored by git), 4 should-fix (async cache clear ordering on workspace switch, Results missing, `sass` in the lock, a network failure on refresh logged the user out), several nits. All fixed or documented above. The ordering fix makes `resetWorkspaceState` synchronous and runs it before the new session is published. Round 2 (Opus 5.5): no BLOCKER; should-fix: other tabs kept a signed-out or different user's cache and token (now: cache is also dropped when the user changes, and sign-out is broadcast to other tabs, with tests), and `pnpm dev` missing from the not-verified list (added). Nits handled: `GENERATOR_NOT_FOUND` added to `RefusalReason`; the department-claim gap recorded in frontend.md §3; the 25 MB limit noted in the README; unused V1 assets removed from `public/`. Open: the `pnpm dev` and browser runs were done afterwards (see the real-stack section); the open points are listed under Not verified. **Gates** stays unticked until the CI job has run on GitHub.
