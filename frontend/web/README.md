# SOPilot web (`frontend/web`)

Next.js 16 (App Router), React 19, TypeScript strict, Tailwind 4, used as a **client-rendered app** ([ADR-010](../../docs/architecture/decisions/adr-010-frontend-stack.md)). Design and constraints: [frontend.md](../../docs/architecture/components/frontend.md). Rules for changes: [.claude/rules/frontend.md](../../.claude/rules/frontend.md).

Implemented (V2-38): same-origin proxy, API client, in-memory session, SSE client, TanStack Query, Vitest. Implemented (V2-15): Google and dev sign-in, shell and navigation, workspace picker and settings, chat with citations, documents list, members (read-only) and knowledge gaps. In review (V2-31): multi-document upload and processing tracking (below). The viewer and administration are V2-32 and V2-33.

## Run

```powershell
cd frontend/web
pnpm install
pnpm dev          # http://localhost:3000
```

core-api and ai-service must be running (see [local development](../../docs/operations/local-development.md)). Backend targets are **run-time** server-side variables read by `proxy.ts`; copy `.env.example` to your own env file and adjust if the defaults (`http://localhost:8080`, `http://localhost:8000`) do not fit.

| Variable | Used by | Meaning |
|---|---|---|
| `CORE_API_URL` | `proxy.ts` (run time) | core-api base URL; receives `/api/v1/**` |
| `AI_SERVICE_URL` | `proxy.ts` (run time) | ai-service base URL; receives `/ai/v1/**` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | build time | Google sign-in button on `/login` (decided in V2-15: stays build time, local only); empty shows a notice and leaves the dev sign-in |

core-api's `SOPILOT_FRONTEND_ORIGIN` must equal the origin of the page (`http://localhost:3000` for `pnpm dev` and for the compose `web` service); refresh and logout check the `Origin` header.

The browser only talks to its own origin. There is no `NEXT_PUBLIC_API_URL`.

A request body above 25 MB is rejected by Next itself with a 500 before it reaches core-api (whose limit is 20 MB and which answers `413 FILE_TOO_LARGE`), so upload code must check the size on the client first.

## Scripts

| Command | Purpose |
|---|---|
| `pnpm build` | production build (standalone output; type-checks under `strict`) |
| `pnpm lint` | ESLint, zero errors expected |
| `pnpm test` | Vitest unit tests (`**/*.test.ts`, Node environment) |

Repo-level: `./scripts/validate-build.ps1 -Scope web` runs build, lint and test.

## Layout

| Path | Contents |
|---|---|
| `proxy.ts`, `lib/server/proxy-target.ts` | same-origin proxy to core-api and ai-service; `next.config.ts` sets `compress: false` (SSE must not be buffered) and `experimental.proxyClientMaxBodySize` above core-api's 20 MB upload limit |
| `lib/api/` | the only `fetch` caller: core-api adapter (envelope, errors, `traceId`), ai-service adapter (plain JSON, `{detail}`), contract types |
| `lib/session/` | in-memory access token, refresh single-flight (Web Locks, `BroadcastChannel` fallback), dev login, switch workspace, sign-out |
| `lib/sse/` | SSE parser, `streamAnswer` (fetch stream with defined end states), answer reducer, open-stream registry |
| `lib/query/` | TanStack Query v5 client, workspace-scoped keys, `resetWorkspaceState` |
| `store/session-store.ts` | Zustand session view (user, workspace); memory only |
| `providers/` | `QueryProvider`, `SessionProvider` (restores the session from the HttpOnly cookie) |
| `app/(app)/`, `components/app/`, `components/chat/`, `lib/chat/` | V2-15 screens, shell, chat and its pure logic |
| `lib/upload/`, `store/upload-store.ts`, `components/documents/` | V2-31 upload: `queue.ts` (pure state machine: 10 files per batch, 3 in flight, per-file state and retry), `failure.ts` (API error → message and action), `validate.ts` (client type and size check), `controller.ts` (requests and polling, outside React), the store, and `UploadDialog` / `UploadManager` mounted in the `(app)` layout |
| `lib/api/endpoints.ts`, `lib/query/hooks.ts` | typed endpoint calls and workspace-keyed queries |
| `components/ui/` | carried-over CSS-module primitives, frozen; new UI is Tailwind 4 on the tokens in `app/globals.css` (V2-15 decision) |

## Upload behaviour (V2-31)

- One `POST /api/v1/documents` per file (no batch endpoint), at most 10 files per batch and 3 requests in flight. Files are checked in the browser first (PDF or Markdown, at most 20 MB); a refused file is listed as failed with its own reason and takes a slot until removed or replaced.
- The batch lives in the `(app)` layout, not in the dialog: closing the dialog never cancels an upload, and a small button reopens it. The browser's leave-page warning is on only while a file is uploading or waiting to be sent. A workspace switch or sign-out aborts the batch (R7) and asks for confirmation first while files are still being sent.
- After the upload only "Processing" is shown. Status polling (`GET /documents/{id}`, rounds 3 s apart, never overlapping) runs only while some file is processing and gives up after 5 failed reads (the row offers Retry). The documents list has its own 5 s refresh while any listed document is not finished.
- Failure actions follow TECH-V2-core-api §5.5: network error → Resend; transient error → Retry; content error → Replace file or Remove. For a stored document that failed while processing, Retry calls `POST /documents/{id}/retry`, Replace file uploads a new version, Delete asks for confirmation.
- Uploads are `WORKSPACE`-visible with no category or tags (department visibility and metadata are V2-33). The Upload button shows only for the workspace publisher (`GET /members/me` → `publisherOf.workspace`); the server stays the authority.
- A duplicate links to `/documents?q=<title>` (title search on the list). `lib/upload/guard.ts` holds the leave prompt; the shared `Modal` traps and restores keyboard focus.

## Docker

The image is built from `Dockerfile` (standalone `node server.js`) and needs `CORE_API_URL` and `AI_SERVICE_URL` at run time. `docker-compose.v2.yml` sets them to the compose service names.
