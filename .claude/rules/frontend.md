---
paths:
  - "frontend/web/**"
---

# frontend/web (Next.js 16 App Router, React 19, TypeScript strict, Tailwind 4)

- Direction: [ADR-010](../../docs/architecture/decisions/adr-010-frontend-stack.md) and ticket V2-38 rebuild the foundation (one `fetch` client, in-memory access token, SSE client, TanStack Query v5, Vitest, `proxy.ts` with `compress: false`, English UI, V1 code removed). Until V2-38 lands, the baseline below applies; do not add new V1-style code.
- Current state: still wired to V1. `next.config.ts` rewrites `/api/v1/*` to `api-gateway:3001`, and `lib/api.ts` keeps Bearer tokens in `localStorage`. V2-38 (then V2-15, V2-31..33) changes it in place to talk to core-api/ai-service. Follow the ticket and TECH-V2-core-api for V2 auth/session. Do not extend the V1 token handling.
- UI work is orchestrated by the global `frontend-delivery` skill (see the global CLAUDE.md).
- New HTTP calls go through the `ApiClient` in `lib/api.ts` (streaming chat uses `fetch` + `ReadableStream` inside it). Baseline exceptions, not to be copied: a second axios client in `services/api-client.ts`, and direct `fetch` in `app/documents/page.tsx`, `components/documents/PreviewModal.tsx` and `services/document.service.ts`. Not machine-checked.
- Server state: `react-query` v3 hooks in `hooks/`. Client state: Zustand 5 in `store/`. Types: `types/` and `interfaces/`; extend the shared type, do not redeclare it in a component.
- UI primitives: reuse `components/ui/*` (barrel `components/ui/index.ts`) and `lucide-react` icons before writing new ones. Style with Tailwind and the tokens in `app/globals.css`.
- No `any` (`eslint-config-next/typescript`). User-facing copy is English.
- Gates: `./scripts/validate-build.ps1 -Scope web` (`pnpm build`, which type-checks under `strict`, then `pnpm lint`). There is no test runner yet; V2-38 adds Vitest. Do not add one outside that ticket.
- A green build is not visual verification. Report whether the page was opened in a browser. If it was not, say so.