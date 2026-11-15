---
paths:
  - "frontend/web/**"
---

# frontend/web (Next.js 16 App Router, React 19, TypeScript strict, Tailwind 4)

- Foundation: [ADR-010](../../docs/architecture/decisions/adr-010-frontend-stack.md), implemented by V2-38. Client-rendered Next.js; screens are client components; no server-side data fetching, Server Actions or BFF.
- Same origin only: use relative URLs (`/api/v1/**`, `/ai/v1/**`); `proxy.ts` reads `CORE_API_URL` / `AI_SERVICE_URL` at run time. Never add `NEXT_PUBLIC_*` backend URLs or `rewrites()`; keep `compress: false` (SSE).
- HTTP: only `lib/api/http.ts` calls `fetch` (`coreRequest`, `coreRequestPage`, `aiRequest`, `authorizedFetch`; streaming is `lib/sse/stream.ts`). No axios, no direct `fetch` in components. Contract types are declared once in `lib/api/types.ts`; extend them, do not redeclare them in a component.
- Session: the access token stays in memory (`lib/session/token.ts`); never in `localStorage`, `sessionStorage`, URLs or logs. Refresh goes through `lib/session/refresh.ts` (single-flight across tabs). A workspace switch must go through `switchWorkspace` so caches and streams are cleared.
- Server state: TanStack Query v5 only; query keys start with the workspace id (`workspaceKey`). Client state: Zustand, small (session, UI). No second data-fetching approach.
- Errors shown to users are the API's fixed message or a local fixed string plus the `traceId` (`describeError`), never a raw exception.
- Markdown from documents or the model renders without raw HTML (no `rehype-raw`).
- UI work is orchestrated by the global `frontend-delivery` skill. Reuse `components/ui/*` and `lucide-react` icons before writing new ones; one styling system, chosen in V2-15 (do not grow a second one). User-facing copy is English.
- No `any` (`eslint-config-next/typescript`), no new `console.*`, every `TODO` has a ticket id.
- Tests: Vitest (`pnpm test`, Node environment, `**/*.test.ts`) for pure logic: refresh, SSE parser, error adapters, upload queue, offset mapping. No other test tooling without agreement.
- Gates: `./scripts/validate-build.ps1 -Scope web` (`pnpm build`, `pnpm lint`, `pnpm test`).
- A green build is not visual verification. Report whether the page was opened in a browser. If it was not, say so.