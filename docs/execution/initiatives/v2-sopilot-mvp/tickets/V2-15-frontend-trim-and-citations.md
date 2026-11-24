---
id: V2-15
title: "Frontend: V2 shell, sign-in/workspace, chat and gaps"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-15
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-11, V2-13, V2-29, V2-30, V2-38]
blocks: [V2-17, V2-31, V2-32, V2-33, V2-50]
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

## 5. Progress notes and evidence (2026-11-15, `done`: owner accepted 2026-11-15, PR #17, CI green)

Branch `feat/web-v2-workspace-citations`, from `develop` (V2-38 was `review` when this started and is `done` since 2026-11-15).

**Decisions (owner, 2026-11-15)**
- Visual direction "Ink & Teal" (A): cool slate neutrals, deep teal accent `#0F766E`, dark ink sidebar, 8px radius, Inter, light mode only. Chosen as the quick option: a polish pass with third-party components may follow if time allows.
- Styling system: Tailwind 4 utilities on the CSS-variable tokens in `app/globals.css`. The carried-over `components/ui/*` CSS-module primitives are frozen (no new modules; their colours follow the tokens) and are replaced in the polish phase.
- Members and invitations are read-only lists here; invite, edit and suspend are V2-33. The workspace usage line shows counts only. The Google client id stays build-time.

**Built:** Google sign-in (GIS button, nonce, `POST /auth/google`) plus the dev sign-in; shell with role-aware navigation and a narrow-screen drawer; workspace switcher, picker and create; chat (POST SSE stream, inline citation chips, old-version label, refusal by reason, `done.warnings`, feedback with comment, conversation list with rename and delete, hidden history entries); documents list (status, filters, cursor paging, polling while processing, download); members and invitations (read-only); knowledge gaps (open and resolved, resolve with note); workspace settings (rename, usage, leave, delete OWNER-only with typed name, PERSONAL protected).

**Wireframe fields checked against the code**
- Gaps "Flagged as" is real: `refusalReason`, `downvotes`, `upvotes`, `comments[]`, plus `askedAt`, `resolvedAt`, `resolutionNote`. The response is a bare array with no total or `hasMore`, so "Open (3)" is not shown and "Load more" appears when a page is full.
- Workspace usage: `GET /workspaces/current` returns `documentCount` and `bytesUsed` only. The limits (50 documents, 200 MB) are server env, so "12 / 50" needs a core-api change; not made.
- `GET /workspaces` items carry `status`, which the V2-38 `WorkspaceView` type lacked (added as optional).
- `done.warnings` are not stored: the history endpoint returns none, so the frontend keeps them in memory per message for the session (lost on reload).

**Verification so far**
- `./scripts/validate-build.ps1 -Scope web` passed (build, lint, test; Vitest 55 tests in 7 files).
- Real stack (compose infrastructure, core-api and ai-service containers, `pnpm dev`; Playwright 1.65.1 headless, installed in the session scratchpad only): sign-in, navigation by role, create, rename and delete a workspace, empty states of documents, members, invitations and gaps, a real SSE question (the empty workspace returns an `INPUT_INVALID` refusal card), new conversation URL and sidebar entry, narrow-screen drawer, sign-out. final run after the review fixes: Chromium 19 of 19 and Firefox 18 of 19; the one failing line is the script's own refusal-detection timing, not the app (the same run's later assertions and a separate focused run confirm the behaviour).
- Mock-backed (answer stream, history, gaps and documents canned in the browser with `page.route`, because the local database has no documents and no LLM answer): citation chips and stored-passage panel, old-version label, figures warning, raw HTML not executed and external images turned into links, feedback with comment, hidden and refusal history entries, document statuses with polling, gap resolve, narrow layout. Chromium and Firefox 17 of 17 each. A further mock-backed script for the review fixes (closest documents kept after the history reload, retry continues the created conversation, a workspace switch drops the live turn) passed 3 of 3 in both browsers.
- Screenshots (local, git-ignored): `docs/quality/evidence/v2-15/` (`chromium-*` and `firefox-*` real stack, `*-states-*` mock-backed, `chat-result.png` real refusal).
- Not verified: a real cited answer from seeded documents (needs documents `READY` and a warm LLM), Google sign-in (no client id configured), a person using the app by hand, Safari and Edge, dark mode (deferred).

**Review (fresh Opus 5.5 `v2-reviewer`, round 1, 2026-11-15)** found 2 blockers and 6 warnings; all were fixed in the tree: the closest documents of a `NO_EVIDENCE` refusal vanished when the history reloaded (now kept in memory per message with the warnings); a live turn survived a workspace switch (the chat view is now keyed by workspace id and conversation id); stopped turns stored as `ERROR` show an "interrupted" note; a retry continues the conversation the server already created; a new question is blocked until the history reload settles; the Google nonce is fetched again after a failed attempt; the status line in `frontend.md` and the PLAN row were corrected. Notes taken: `exit.ts` only picks `ACTIVE` workspaces; the gaps query waits for an OWNER or ADMIN role. Not taken: the vote is not shown again after a reload (history returns no vote), `[n]` inside code spans is still linked, offset paging of gaps can skip a row after a resolve, and `window.open` after an `await` may be blocked by strict popup blockers; all are small and listed for the polish phase.

**Review round 2** (second fresh Opus 5.5 `v2-reviewer`): no blockers, 5 warnings. Fixed: a changed vote no longer erases the saved comment; leave or delete is not repeated when only the move to another workspace failed; the new-conversation redirect is skipped if the user already left the chat; a retry falls back to a new conversation when the id from `meta` was never stored; a Google nonce older than 4 minutes is refreshed when the login tab is shown again. Also changed: neutral copy for stored `ERROR` turns, the `info` token is now blue (so Processing is not the accent colour), separate error state per dialog. Left for the polish phase: no retry button after Stop, a 404 conversation URL still shows the composer, a stopped turn may reach the sidebar late, some stored failure messages are Vietnamese (a copy decision), Google sign-in unverified in a browser.
