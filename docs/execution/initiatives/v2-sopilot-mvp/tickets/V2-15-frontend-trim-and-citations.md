---
id: V2-15
title: "Frontend: V2 shell, sign-in/workspace, chat and gaps"
type: feat
status: todo
created: 2026-10-17
updated: 2026-11-14
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-11, V2-13, V2-29, V2-30, V2-38]
blocks: [V2-17, V2-31, V2-32, V2-33]
branch: "feat/web-v2-workspace-citations"
assignee: pair
---

# TICKET V2-15: Frontend V2

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
Keep the chat components; remove the system admin pages, analytics, roster, the V1 department tree, OnlyOffice, version comparison and the model-picker UI. Flat V2 departments belong to V2-33. Orchestrated by the `frontend-delivery` skill (global CLAUDE.md). Changed 2026-10-21 per [AUDIT-markdown-normalization](../../../../research/audit-markdown-normalization-and-preview-2026-10-21.md) §4: the ≤ 10-file upload flow and the "Nội dung hệ thống nhận diện" (recognized content) view (PRD-V2 FR-30, FR-31, UC-12). Split from XL on 2026-10-24: upload is V2-31, the viewer V2-32, administration V2-33; every criterion kept, no added scope.

## 2. Acceptance criteria
- [ ] Google sign-in; choosing/switching workspaces; tokens kept per workspace (T8).
- [ ] The navigation shell: chat, documents, members + invitations, knowledge gaps, workspace settings; the document detail/administration screens are in V2-31/V2-32/V2-33.
- [ ] Changed 2026-10-21 (owner decision D10, TECH-V2-ai-service §7.5): a citation with `isCurrentVersion = false` shows the stored passage with an "Old version" label and does **not** open the viewer (`/content` serves only the current version). Show `refusal` by `reason`: `NO_EVIDENCE` with the closest documents, `OUT_OF_SCOPE` and `INPUT_INVALID` without; show `done.warnings` (`NUMBER_NOT_IN_SOURCES`) as a reminder to "check the figures against the source".
- [ ] Show the "not found" refusal and document processing status.
- [ ] Changed 2026-11-14 (owner decision, frontend inventory gaps): conversation list per workspace with rename and delete, visible only to the creator (FR-15), and answer feedback with upvote/downvote and an optional comment (FR-16; the API is V2-13).
- [ ] Changed 2026-11-14: the workspace settings screen covers create, rename and delete (delete OWNER-only) of workspaces (FR-03). Domain join (FR-05) and CSV member import (FR-24) are P1 and have no frontend in this ticket.
- [ ] Remove the unused OpenAI model enum and every call to the old gateway (the structural removal of V1 code is V2-38; verify here that none remains).
- [ ] `pnpm build`, `pnpm lint` and `pnpm test` stay green (V2-38 owns clearing the 61 V1 lint errors).
- [ ] **Check in a real browser** the sign-in/workspace choice/chat/knowledge-gap flows in this ticket's scope (including a narrow-screen layout); upload/viewer/administration are accepted in V2-31/V2-32/V2-33; state clearly if not checked (build/lint do not replace it).

## 3. Guide
- **Changed 2026-11-14 ([ADR-010](../../../../architecture/decisions/adr-010-frontend-stack.md)):** [V2-38](V2-38-frontend-foundation.md) builds the foundation first (proxy, API client, session, SSE client, TanStack Query, Vitest, V1 removal). This ticket builds the screens on it. Start with the visual direction and a minimal design system (tokens, primitives, one styling system) through `frontend-delivery`, before the screens.
- **Files:** `frontend/web/` per `.claude/rules/frontend.md`; the API client built by V2-38 in `frontend/web/lib/`; types `frontend/web/types`.
- **Keep a working demo during the transition (ADR-004 §4.5):** the frontend is changed in place, so once V2-38 stops it calling the old gateway it no longer runs against the old stack.
  - Start wiring APIs only once the tickets in `depends_on` have working endpoints on `docker-compose.v2.yml`; before that, do only the backend-independent UI work (trimming pages, viewer components) on the ticket's branch.
  - The proxy targets (TECH-V2-core-api §1.1) are set up by V2-38 as a `proxy.ts` rewrite reading `CORE_API_URL` (default `http://core-api:8080`) and `AI_SERVICE_URL` (default `http://ai-service:8000`) at run time, so it runs both in compose and with `pnpm dev` on the host. Recorded in `frontend/web/.env.example`.
  - The tag `v1-final` is created by V2-38 before its branch merges (the last commit whose frontend still runs with the old stack). Fallback demo: `git checkout v1-final` + the old `docker-compose.yml`. V2-17 reuses this tag.

## 4. Testing
```powershell
./scripts/validate-build.ps1 -Scope web
```
Plus notes on the flows tried by hand in the browser.
