---
title: "Frontend (frontend/web): current state and V2 direction"
status: approved
created: 2026-11-13
updated: 2026-11-16
author: "Owner"
affected_services: [web]
affected_schemas: []
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-010-frontend-stack.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-38-frontend-foundation.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-15-frontend-trim-and-citations.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-31-frontend-document-upload.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-32-frontend-source-viewer.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-33-frontend-member-metadata-admin.md
---

# Frontend (frontend/web)

> **Direction (2026-11-14):** [ADR-010](../decisions/adr-010-frontend-stack.md) keeps Next.js as a client-rendered app and rebuilds the foundation in [V2-38](../../execution/initiatives/v2-sopilot-mvp/tickets/V2-38-frontend-foundation.md) before V2-15. The feature list and requirements are in [the inventory](frontend-feature-inventory.md) and [NFRs](frontend-nfrs.md).
>
> **Implementation status:** the foundation (sections 1 and 2) is implemented by V2-38 and waits for owner review. The V2-15 screens (section 4) are implemented on branch `feat/web-v2-workspace-citations` and in progress. It was exercised against the real core-api and ai-service in headless Chromium and Firefox (Playwright); the ticket's Results list what was not verified, including a reload during an in-flight refresh that can end the session (strict refresh rotation, a core-api decision). V2-15 adds Google and dev sign-in, the shell and navigation, the workspace picker and settings, chat, documents (read-only), members (read-only) and knowledge gaps (section 4); upload and the source viewer are V2-31 and V2-32 (done); administration is V2-33 (implemented, in review, section 4). The V1 UI is tagged `v1-final` in git; its description is archived at [v1-context/architecture/frontend.md](../../archive/v1-context/architecture/frontend.md).

## 1. Stack and layout

- Next.js 16 (App Router, client-rendered, no server data fetching), React 19, TypeScript strict, Tailwind 4, Zustand 5 (session view only), `@tanstack/react-query` v5, Vitest. Versions are in `frontend/web/package.json`.
- `app/`: `layout.tsx` (providers), `page.tsx` (empty home), `login/page.tsx` (dev login). All V1-only pages (passwords, sessions, analytics, admin, documents, chat) and the i18n layer were removed, together with `rehype-raw`, `axios`, `recharts`, `mammoth`, `sass`, `jwt-decode`, `dompurify`, `mark.js`, `react-hot-toast` and the legacy `react-query` v3 package.
- `lib/api/` (the only `fetch` caller; core-api and ai-service adapters, contract types), `lib/session/` (token in memory, refresh single-flight, login, switch workspace, sign-out), `lib/sse/` (parser, `streamAnswer`, answer reducer, stream registry), `lib/query/` (client, workspace-scoped keys, `resetWorkspaceState`), `lib/server/proxy-target.ts`, `store/session-store.ts`, `providers/`, and the carried-over `components/ui/*` primitives (their styling is decided in V2-15).
- `react-markdown` and `remark-gfm` stay for the Markdown views of V2-15 and V2-32 (no `rehype-raw`).
- UI work follows `.claude/rules/frontend.md` and the `frontend-delivery` skill. Run and env: [frontend/web/README.md](../../../frontend/web/README.md).

## 2. How it talks to the backend

- **Same origin only.** The client uses relative URLs (`/api/v1/**` to core-api, `/ai/v1/**` to ai-service). `proxy.ts` (Next 16 proxy) rewrites them to `CORE_API_URL` and `AI_SERVICE_URL`, read at run time (`rewrites()` would freeze them at build time). `next.config.ts` sets `compress: false` so SSE is not buffered and raises `experimental.proxyClientMaxBodySize` above core-api's 20 MB upload limit (ADR-010 §4.3).
- **Client.** `lib/api/http.ts` attaches the Bearer token and, on `401`, refreshes once and retries. core-api responses are unwrapped from `{data, traceId}`; errors become `ApiError` with the API's fixed message, `code` and `traceId`; ai-service errors use `{detail}`. Unknown shapes get a local fixed message.
- **Session.** The access token lives in a module variable (`lib/session/token.ts`). On load, `SessionProvider` refreshes through the `HttpOnly` cookie. Refreshes are merged: one promise per tab, a Web Lock across tabs (a tab that waited re-uses the result the other tab broadcast), and a `BroadcastChannel` claim when Web Locks are missing. The broadcast carries the new session between same-origin tabs and is not persisted.
- **Workspace switch.** `POST /auth/switch-workspace`, then every open stream is aborted and the TanStack Query cache cleared; other tabs do the same when they receive the new session (R7).
- **Streaming.** `streamAnswer` reads `POST /ai/v1/conversations/{id|new}/messages` with `fetch` and ends as `done`, `error`, `cancelled` or `interrupted`. `reduceAnswer` applies `delta`, `replace`, `refusal` and `done.finalText`.
- There is no `middleware.ts` route protection; pages redirect client-side when the session is anonymous. The server stays the authority (another workspace's object is `404`).

## 3. V2 constraints

- **Sessions:** the V2 refresh token is an `HttpOnly; SameSite=Strict` cookie on `/api/v1/auth` (see [identity and access](../domain/identity-and-access.md)); the access token (≤ 15 minutes) stays in memory, not `localStorage`. Refresh rotation is strict, so concurrent refreshes from several tabs must be merged into one request, otherwise the second one counts as reuse and revokes the session (V2-29 review note).
- **APIs:** core-api under `/api/v1/**` with the `{"data", "traceId"}` envelope; ai-service under `/ai/v1/**` with plain JSON and SSE for answers. See [HTTP conventions](../api/http-conventions.md).
- **Markdown rendering:** no `rehype-raw` (removed with the V1 chat and viewer code); V2-32 renders canonical Markdown without raw HTML and turns external images into links.
- **Workspace and role** are the token's `wid` and `wrole` (and `wdept`); the V2-38 client reads workspace and role from the login/refresh response (`LoginResponse.workspace`), which has no department yet, so V2-15/V2-33 need `GET /members/me` or a contract change for department-dependent UI. The UI hides actions the role cannot do, but the server is the authority (another workspace's object is `404`).
- **Verification:** a green build is not visual verification. Each UI ticket records browser evidence per acceptance criterion and says which browsers were not checked.

## 4. V2-15 screens and visual direction (in progress)

- **Routes** (`app/`): `/login`; inside the authenticated shell `(app)`: `/chat` and `/chat/<id>` (one optional catch-all), `/documents`, `/members` (OWNER/ADMIN; tabs for members, invitations, departments, categories and, for OWNER, publishers, V2-33), `/gaps` (OWNER/ADMIN), `/audit` (OWNER, V2-33), `/settings`, `/workspaces`; outside the shell the public `/invite` (V2-33). `/` redirects to `/chat`. Upload (V2-31) is a dialog on `/documents`; the document page `/documents/[id]` (V2-32) is the recognized-content screen; document metadata and access are a dialog opened from both (V2-33).
- **Code:** `lib/api/endpoints.ts` (typed calls), `lib/query/hooks.ts` (workspace-keyed queries, document polling only while something is processing), `lib/chat/` (citation linking, live turn state, labels, in-memory warnings), `components/app/` (shell, workspace switcher), `components/chat/`.
- **Upload (V2-31, in review):** the batch state is a pure queue (`lib/upload/queue.ts`, Vitest) driven by `lib/upload/controller.ts` outside React and mounted once in the `(app)` layout, so closing the dialog never cancels an upload (frontend-nfrs R2); status polling runs only while some uploaded document is processing (R3). Uploads are `WORKSPACE`-visible; department visibility and metadata stay with V2-33.
- **Viewer (V2-32, in progress):** `components/viewer/ContentViewer` is shared by `/documents/[id]` (FR-31) and the citation dialog (FR-14). The Markdown renders through `SafeMarkdown` (react-markdown without `rehype-raw`; images become links); blocks overlapping the cited range are marked from the Markdown AST positions, and the "Markdown source" view marks the exact range. The server returns citation offsets in **code points** (only `pages` also carry `charStart16`/`charEnd16`), so the frontend converts them with `lib/viewer/offsets.ts` (pure, Vitest with emoji). The original PDF is the native viewer in an iframe at `#page=N` from a signed URL requested on demand (frontend-nfrs R5). In chat, an expanded source renders its stored `snippet` as Markdown through `SafeMarkdown` (tables and headings, clamped height), and refusal text renders as Markdown too. While the model reasons, `components/chat/ReasoningBlock` shows the `reasoning` stream events as a collapsible block (open and live while thinking, "Thought for N s" after `reasoning_done`); it is fed by the live turn only, because reasoning is not stored yet.
- **Administration and metadata (V2-33, in review):** pure rules live in `lib/admin/` (Vitest): `metadata.ts` builds the `PATCH /documents/{id}` body from the changed fields only and validates the form; `planAccess` maps an access change to the right call, because core-api refuses a publisher's scope switch or owner-department change with `409 OWNERSHIP_CHANGE_REQUIRES_OWNER` (ADR-009 decision 8): within the same scope `PUT /visibility`, otherwise an OWNER-only `PUT /ownership` (the UI explains the block to others instead of sending the call). Role gates: members, departments and categories OWNER/ADMIN, publishers and the audit log OWNER; plain members never call `GET /members` (it is `403` for them). The invitation link is shown once and never stored; `/invite` takes the token from the URL fragment, clears it from the address bar and keeps it in memory. Departments are hidden in a personal or single-member workspace. Known gaps seen from the UI: no list of documents with an unapplied category proposal and no bulk category assignment (V2-25 section 2a: a later ticket); document code, revision and effective date are not editable (no version-level endpoint).
- **Visual direction (updated 2026-11-24):** Refined "Ink & Teal" supporting both Light and Dark modes (`next-themes`, `sopilot-theme` preference key only, never tokens): cool alabaster/obsidian surfaces, teal accent (`#0F766E` light / `#14B8A6` dark), Deep Ink collapsible sidebar, `Plus Jakarta Sans` + `JetBrains Mono` loaded via `next/font/google` (`latin` + `vietnamese`). Status colours (success, warning, danger, info) stay separate from the accent and pair with words or icons.
- **Styling & motion system:** Tailwind 4 utilities over the CSS-variable tokens in `app/globals.css`. All legacy CSS-module primitives in `components/ui/*` were replaced with Tailwind 4 + `class-variance-authority` + selective Radix UI primitives (`Dialog`, `Popover`, `Switch`) + `motion` (`MotionConfig reducedMotion="user"`), `sonner` toasts, `cmdk` command palette (`Ctrl+K`), and owned CSS/Canvas2D effects in `components/effects/*`. Native `<select>` keeps `select-clean` (`appearance: none` + `::picker-icon { display: none }`) for consistent single-caret rendering and Playwright `.selectOption()` compatibility.
- **Citations:** `[n]` markers become chips through `cite:` Markdown links; a citation with `isCurrentVersion = false` shows the stored passage and an "Old version" label and never opens the viewer; raw HTML is not rendered and images become links.
- **Known API limits seen from the UI:** the knowledge-gap list has no total; `done.warnings` are not in the history response; the workspace usage endpoint has no limits.
