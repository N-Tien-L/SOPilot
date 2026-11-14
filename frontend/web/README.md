# SOPilot web (`frontend/web`)

Next.js 16 (App Router), React 19, TypeScript strict, Tailwind 4, used as a **client-rendered app** ([ADR-010](../../docs/architecture/decisions/adr-010-frontend-stack.md)). Design and constraints: [frontend.md](../../docs/architecture/components/frontend.md). Rules for changes: [.claude/rules/frontend.md](../../.claude/rules/frontend.md).

Implemented so far (ticket V2-38): same-origin proxy, API client, in-memory session, SSE client, TanStack Query, Vitest and a minimal shell (dev sign-in, empty home, sign-out). Google sign-in, the workspace picker and chat are V2-15; upload, viewer and administration are V2-31 to V2-33.

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
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | build time | Google sign-in (V2-15 decides whether it becomes run time) |

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
| `components/ui/` | carried-over primitives; V2-15 decides their styling |

## Docker

The image is built from `Dockerfile` (standalone `node server.js`) and needs `CORE_API_URL` and `AI_SERVICE_URL` at run time. `docker-compose.v2.yml` sets them to the compose service names.
