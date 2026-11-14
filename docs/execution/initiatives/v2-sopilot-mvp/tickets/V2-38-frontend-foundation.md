---
id: V2-38
title: "Frontend foundation: API client, session, SSE client, TanStack Query, Vitest, V1 removal"
type: refactor
status: todo
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
- [ ] **Tag first.** Create the tag `v1-final` on `develop` before this branch merges (it is the last commit whose frontend runs against the old stack; V2-17 reuses the tag).
- [ ] **Proxy.** `/api/v1/**` goes to core-api and `/ai/v1/**` to ai-service through a `proxy.ts` rewrite that reads `CORE_API_URL` and `AI_SERVICE_URL` at run time, with `compress: false` and `experimental.proxyClientMaxBodySize` above core-api's 20 MB upload limit (the default 10 MB cuts larger multipart bodies; ADR-010 §4.3); `rewrites()` is not used. Works in compose and with `pnpm dev`; the variables are in `frontend/web/.env.example`. The `docker-compose.v2.yml` and `.github/workflows/ci.yml` edits this ticket needs prompt for approval (CLAUDE.md #8); the Dockerfile does not.
- [ ] **Same origin only.** The client uses relative base URLs. `NEXT_PUBLIC_API_URL` is removed from the code (`lib/api.ts`, `services/api-client.ts`, `services/document.service.ts`), the Dockerfile, the compose build args and the README, so no request bypasses the proxy. The compose `web` service gets `CORE_API_URL` and `AI_SERVICE_URL` as run-time env (and `depends_on` ai-service). `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is a build-time value today; V2-15 decides whether to keep it build-time or expose it at run time. core-api's `SOPILOT_FRONTEND_ORIGIN` must match the web origin in both run modes.
- [ ] **API client.** One `fetch`-based client with a core-api adapter (envelope, `{error:{code,message,details}}`, `traceId`) and an ai-service adapter (plain JSON, `{detail}`), typed per contract (M1, M2). `axios`, the second client and direct `fetch` calls are gone. Errors surface a fixed message and the `traceId` where present (S4, O2).
- [ ] **Session.** Access token in memory only; refresh through the `HttpOnly` cookie; concurrent refreshes from several tabs merge into one request via Web Locks with a `BroadcastChannel` fallback (C5, R1). Nothing token-like in `localStorage`, `sessionStorage`, URLs or logs (S1). Workspace switch calls `POST /auth/switch-workspace`, clears all cached server state and aborts open streams (R7).
- [ ] **SSE client.** `fetch` + stream reader for `POST /ai/v1/conversations/{id|new}/messages`: parses `meta`, `delta`, `replace`, `refusal`, `citations`, `done`, `error`; supports cancel; a broken or cancelled stream ends in a defined state (R4).
- [ ] **Server state.** `@tanstack/react-query` v5 provider and conventions; the legacy `react-query` v3 package is removed (one data-fetching approach, M5).
- [ ] **Vitest.** Runner configured with `pnpm test` (owner-approved 2026-11-14, C10). Unit tests for refresh single-flight, the SSE parser, both error adapters, and cache clearing on workspace switch. V2-31 and V2-32 add their own tests (upload queue, UTF-16 mapping) on this setup.
- [ ] **V1 removal.** Delete V1 pages, components, services and stores that V2 does not use (list in ADR-010 §2.7 and the PRD §5 UI row), `lib/i18n.ts` and the language preference, and the dependencies only they use (`recharts`, `mammoth`, `sass`, `rehype-raw`, `axios`). Chat message rendering no longer uses `rehype-raw` (S2). A minimal shell stays: sign-in (dev login in `local`), a workspace-aware empty home, sign-out.
- [ ] **Gates.** `pnpm build`, `pnpm lint` (zero errors: this ticket owns clearing the 61 V1 lint errors) and `pnpm test` pass. `scripts/validate-build.ps1` runs `pnpm test` for the web scope, and the CI frontend job runs `pnpm lint` and `pnpm test` as well as the build (it runs only the build today).
- [ ] **Dependencies.** Every remaining dependency is kept on purpose. Decide `dompurify`, `mark.js`, `jwt-decode` and `react-hot-toast` (keep or remove, one line each in the Results section); remove the self-dependency `"web": "file:"` in `package.json`.
- [ ] **Browser check** (Chrome and Firefox, against core-api and ai-service from source): dev login; storage shows no token; two tabs refreshing at once keep the session; workspace switch clears the previous workspace's data; a streamed answer reaches the page incrementally through the proxy (not in one chunk); a 15 to 20 MB PDF uploaded through the proxy reaches core-api with the same SHA-256 (no truncation). State anything not checked.
- [ ] **Compose image.** Build the `web` image once (standalone `node server.js`, not `next start`) and start it with two different `CORE_API_URL` values: requests follow the run-time value, streaming stays incremental, and an upload of about 15 MB succeeds.
- [ ] **Docs.** Update `docs/architecture/components/frontend.md` (§1 to §3 to the real state), `.claude/rules/frontend.md`, `frontend/web/README.md` and `.env.example`.

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
*(Fill in when running: commit, command results, browser notes.)*
