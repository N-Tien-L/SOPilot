---
id: ADR-010
title: "V2 frontend: keep Next.js as a client-rendered app and rebuild the foundation"
status: approved
created: 2026-11-14
updated: 2026-11-14
author: "Owner"
deciders: ["Owner"]
amends: []
supersedes: []
superseded_by: []
refs:
  - docs/architecture/components/frontend-feature-inventory.md
  - docs/architecture/components/frontend-nfrs.md
  - docs/architecture/components/frontend.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
---

# ADR-010: Frontend stack and foundation

> **Status:** `approved` (owner decision 2026-11-14), proposed the same day. The spike in §4.3 passed with two config changes. Inputs: [feature inventory](../components/frontend-feature-inventory.md) and [NFRs and constraints](../components/frontend-nfrs.md) (constraint ids `C#`, requirement ids `S#/R#/P#/U#/M#/O#` refer to that page).

## 1. Context

V2-15 and its three follow-ups (V2-31, V2-32, V2-33) assume the V1 frontend is "changed in place". The question was whether the stack, or the structure around it, fits the V2 app.

What the code shows today (checked 2026-11-14 in `frontend/web`):

- About 26,000 lines of TypeScript. Much of it is V1 features V2 cuts: admin users, departments tree, metadata, analytics, sessions, password flows, OnlyOffice-era document pages.
- `lib/api.ts` is 2,786 lines and keeps tokens in `localStorage`; a second axios client and direct `fetch` calls sit beside it ([frontend rule](../../../.claude/rules/frontend.md)).
- The server-state layer is thin: the legacy `react-query` v3 package is imported in 2 files, `axios` in 2, Zustand in 3. Docs say "TanStack Query"; the package is the old line.
- `lib/i18n.ts` (1,285 lines) is a Vietnamese/English translation layer, now unneeded: the UI is English (owner decision 2026-11-14, NFR §5).
- 49 CSS modules coexist with Tailwind 4 and `sass`; there are two styling systems.
- `next.config.ts` proxies `/api/v1/*` to the V1 gateway with build-time rewrites, which the spike (§4.3) shows cannot take run-time targets and buffer SSE. In practice the V1 client does not use the proxy: `lib/api.ts`, `services/api-client.ts` and `services/document.service.ts` call the backend cross-origin through the build-time `NEXT_PUBLIC_API_URL` (Dockerfile, `docker-compose.v2.yml` build args), so V2-38 must switch them to relative URLs. *Note 2026-11-17: `docker-compose.v2.yml` was renamed to `docker-compose.yml` in V2-17, after the V1 compose file was removed; the context above is kept as written.*

The NFRs say the app is local-only, logged-in and needs no server rendering (C1). Its hard parts are the auth/session model (C4 to C6), POST-based SSE (C3), a safe Markdown viewer (C8) and an upload queue; none of them depends on the rendering framework. So the framework is not the problem; the V1 foundation is.

## 2. Decision

Keep **Next.js 16 (App Router) and React 19**, used as a client-rendered app, and **rebuild the foundation** inside it instead of trimming V1 code in place.

### 2.1 Framework and rendering
Keep Next.js only for routing, the build, and the same-origin proxy to both backends (C4, C13). The proxy is a `proxy.ts` rewrite reading `CORE_API_URL` and `AI_SERVICE_URL` at run time, with `compress: false` so SSE is not buffered and `experimental.proxyClientMaxBodySize` raised above core-api's 20 MB upload limit so uploads are not cut (§4.3); `rewrites()` is not used. Screens are client components; no server-side data fetching, no Server Actions, no BFF holding tokens. The refresh cookie stays scoped to core-api's `/api/v1/auth` as designed (ADR-005, [identity and access](../domain/identity-and-access.md)).

### 2.2 API layer
One `fetch`-based client with two adapters (core-api envelope and error shape, ai-service plain JSON and `{detail}`), typed per contract (M1, M2). It replaces `lib/api.ts`, the axios client and the direct `fetch` calls, and removes `axios`. SSE is read from `fetch` with a small parser (C3), not `EventSource`.

### 2.3 Session
Access token in memory only (S1). Refresh through the cookie, single-flight across tabs with Web Locks (fallback `BroadcastChannel`) (C5, R1). Switching workspace clears every cache and open stream (R7).

### 2.4 Server state and client state
**TanStack Query v5** (`@tanstack/react-query`) for server state, replacing the legacy `react-query` v3 package: one data-fetching approach (M5). Zustand stays for the small amount of client state (session, UI), since it is already a dependency.

### 2.5 UI copy, styling, components
English strings inline; delete `lib/i18n.ts` and the language preference. One styling system, to be set in the design-direction phase (`frontend-delivery`); this ADR only requires that the V2 UI does not grow a second one. Primitives are rebuilt or reused on that basis, not carried over wholesale. Dark mode is deferred (NFR §5).

### 2.6 Testing
**Vitest** for unit tests of the risky pure logic (M4): refresh single-flight, upload queue, SSE parser, UTF-16 range mapping. Introduced by a ticket (C10). Browser end-to-end tooling is not part of this decision.

### 2.7 Removed
V1 pages and components, `recharts`, `mammoth`, `sass`, `rehype-raw`, axios, the legacy `react-query` package, and the i18n layer leave with the code that uses them (M3). PDFs use the browser's native viewer at `#page=N` (R5); no PDF library.

## 3. Alternatives considered

Ratings are judgments against the NFR priorities (security and tenant safety first, then hard interactions, then maintainability and delivery, then testability), not measurements. `++` clearly good, `+` good, `0` neutral, `−` weak.

| Criterion | A. Trim V1 in place | B. Keep Next, rebuild foundation (**chosen**) | C. Vite + React SPA | D. Next BFF (server holds tokens) |
|---|:---:|:---:|:---:|:---:|
| Security and tenant safety (S, R1, R7) | − (V1 token handling and a 2,786-line client carried over) | ++ | ++ | + (needs a new auth model) |
| Hard interactions (R2 to R5) | 0 | + | + | 0 |
| Maintainability (M1 to M5) | − (mixed patterns, ~26k lines to audit) | + | + | 0 |
| Testability (M4) | 0 | + | + | 0 |
| Delivery cost before V2-15 | ++ (none) | 0 (foundation work first) | − (routing, proxy, Dockerfile and compose changes, a new router dependency) | − |
| Fits fixed constraints (C4, C13, compose) | + | + | 0 (compose is edited, which prompts) | − (contradicts ADR-005 cookie design) |

| Option | Why not |
|---|---|
| A. Trim V1 in place | It keeps the V1 patterns the NFRs reject and makes four L tickets build on code that is mostly being deleted; V2-15 already has to rewrite sign-in, tokens and the client, so the saving is small. |
| C. Vite + React SPA | Viable, since no requirement needs server rendering. But it replaces a working build, Dockerfile and proxy to remove a framework that does no harm here, adds a router dependency (C10), and edits the compose file. The gain, a simpler client/server model, is available by using Next as a client-rendered app (§2.1). Revisit only if the spike in §4.3 fails and no proxy fix exists. |
| D. Next BFF | A server-side token holder changes the approved auth design (ADR-005, V2-29) and doubles the places a tenant can leak. Not justified for a local app. |

## 4. Consequences

### 4.1 Positive
One client, one data approach, one session mechanism; the hard interactions are isolated and unit-testable; the V1 attack surface (`localStorage` tokens, `rehype-raw`, duplicate clients) goes away; four tickets build on a clean base.

### 4.2 Negative and cost
Foundation work comes before visible screens, and the V1 UI is not a working demo during it (V2-38 creates the `v1-final` tag before merging). Existing V1 components are mostly rewritten, not reused. Adds one devDependency (Vitest) and swaps one (TanStack Query v5 for `react-query` v3); both were approved by the owner on 2026-11-14 (C10).

### 4.3 Spike results (2026-11-14)
Throwaway Next 16.1.6 app (same versions as `frontend/web`) with two mock backends, run in the session scratchpad; nothing in the repo changed. Mock SSE emits 5 events 0.6 s apart. Not tested: real core-api and ai-service, a browser, `pnpm dev`, the compose image.

| Check | Result |
|---|---|
| SSE through `rewrites()` with default `compress` | **Buffered.** With `Accept-Encoding: gzip` (browsers send it) the stream arrived in two chunks, the last at 3.1 s; deltas would not show incrementally (breaks P1). |
| SSE with `compress: false` | Incremental, five chunks 0.6 s apart, identical to a direct connection. |
| Runtime proxy targets with `rewrites()` | **Fixed at build time.** Built with target A, started with `CORE_API_URL` pointing at B: requests still went to A. `rewrites()` cannot meet V2-15 §3. |
| Runtime proxy targets with `proxy.ts` (Next 16 middleware) rewriting from `process.env` | Works. One build, started against B then A: followed the run-time env each time, no rebuild. |
| Cookie `HttpOnly; SameSite=Strict; Path=/api/v1/auth` | `Set-Cookie` passes through unchanged, and the cookie is returned to `/api/v1/auth/*` by the browser-side client in both proxy styles (tested with a manual `Cookie` header, so browser cookie-path behaviour itself is not exercised). |

| 15 MB `POST` through `proxy.ts` (default config) | **Fails.** Next buffers proxied request bodies up to `proxyClientMaxBodySize` (default 10 MB): the response was a 500 with "Request body exceeded 10MB". core-api accepts 20 MB uploads (FR-06), so this would break V2-31. |
| Same `POST` with `experimental.proxyClientMaxBodySize: '25mb'` | The upstream received all 15,000,000 bytes. |

Limits of the spike: it used `next start`, not the production standalone server (`node server.js`) that the compose image runs; the mock backends are not core-api or ai-service; no browser was used. V2-38 therefore re-checks the proxy in the compose image and with a real 15 to 20 MB upload.

Consequences for the decision: use a `proxy.ts` rewrite (not `rewrites()`) for `/api/v1/**` and `/ai/v1/**`, set `compress: false` and raise `proxyClientMaxBodySize`. All three are small. Option C is not needed on these grounds.

### 4.4 Follow-ups
- [V2-38](../../execution/initiatives/v2-sopilot-mvp/tickets/V2-38-frontend-foundation.md) delivers the foundation (API client, session with single-flight, SSE client, TanStack Query, Vitest, V1 removal, `v1-final` tag). V2-15 depends on it. Owner approved Vitest and TanStack Query v5 on 2026-11-14 (C10).
- The design-direction phase (styling system, primitives, tokens) through `frontend-delivery`, at the start of V2-15 before the screens in V2-15, V2-31 to V2-33.
- V2-38 updates [frontend.md](../components/frontend.md) and `.claude/rules/frontend.md` to the real state when it lands; until then both describe the V1 baseline and point here.
