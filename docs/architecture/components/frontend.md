---
title: "Frontend (frontend/web): current state and V2 direction"
status: approved
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
affected_services: [web]
affected_schemas: []
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-15-frontend-trim-and-citations.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-31-frontend-document-upload.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-32-frontend-source-viewer.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-33-frontend-member-metadata-admin.md
---

# Frontend (frontend/web)

> **Implementation status:** the frontend is still wired to V1 (the `api-gateway`). V2-15 replaces the shell, sign-in and chat; V2-31, V2-32 and V2-33 add upload, the source viewer and administration. This page records what the code does today (checked on 2026-11-13) and the V2 constraints. The V1 description it replaces is archived at [v1-context/architecture/frontend.md](../../archive/v1-context/architecture/frontend.md).

## 1. Stack and layout

- Next.js 16 (App Router), React 19, TypeScript strict, Tailwind 4, Zustand 5, axios, TanStack Query (`providers/QueryProvider.tsx`). Versions are in `frontend/web/package.json`.
- `app/`: pages for chat (`page.tsx`), `login`, `register`, `forgot-password`, `reset-password`, `documents`, `profile`, `sessions`, `analytics`, `admin`. Several of these are V1 features outside the V2 scope (passwords, sessions, analytics) and go away in V2-15.
- `components/` (`chat`, `documents`, `layout`, `ui`, …), `store/` (`auth-store`, `ui-store`, `preferences-store`), `services/` (per-domain clients on `api-client.ts`), `lib/api.ts` (the typed V1 client, about 2,800 lines), `hooks/useChat.ts`, `types/`, `interfaces/`.
- UI work follows `.claude/rules/frontend.md` and the `frontend-delivery` skill.

## 2. How it talks to the backend today

- `next.config.ts` rewrites `/api/v1/*` to `http://api-gateway:3001/api/v1/*` (V1). There is no route to core-api or ai-service yet.
- `lib/api.ts` keeps the access and refresh tokens in `localStorage` and sends `Authorization: Bearer`; on `401` it refreshes once with the stored refresh token and retries.
- There is **no** `frontend/web/middleware.ts`; routes are not protected server-side. Older context docs described one as a target design.

## 3. V2 constraints the rewrite must meet

- **Sessions:** the V2 refresh token is an `HttpOnly; SameSite=Strict` cookie on `/api/v1/auth` (see [identity and access](../domain/identity-and-access.md)); the access token (≤ 15 minutes) stays in memory, not `localStorage`. Refresh rotation is strict, so concurrent refreshes from several tabs must be merged into one request, otherwise the second one counts as reuse and revokes the session (V2-29 review note).
- **APIs:** core-api under `/api/v1/**` with the `{"data", "traceId"}` envelope; ai-service under `/ai/v1/**` with plain JSON and SSE for answers. See [HTTP conventions](../api/http-conventions.md).
- **Markdown rendering:** `components/chat/ChatMessage.tsx` and `components/documents/DocumentViewerModal.tsx` currently render with `rehype-raw`, which executes raw HTML from model output or documents. V2-32 requires rendering without `rehype-raw`; external images become links.
- **Workspace and role** come from the token claims (`wid`, `wrole`, `wdept`); the UI hides actions the role cannot do, but the server is the authority (another workspace's object is `404`).
- **Verification:** a green build is not visual verification. Each UI ticket records browser evidence per acceptance criterion and says which browsers were not checked.
