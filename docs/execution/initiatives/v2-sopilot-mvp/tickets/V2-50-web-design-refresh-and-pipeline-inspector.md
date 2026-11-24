---
id: V2-50
title: "web: design system refresh (light and dark, Tailwind + CVA + Radix) and the Pipeline Inspector UI"
type: feature
status: done # todo | in_progress | review | done | blocked
created: 2026-11-24
updated: 2026-11-24
author: "Owner"
scope: web
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-15, V2-49]
blocks: [V2-18, V2-48]
blocked_reason: ""
branch: "feat/ai-rerank-toggle"
refs:
  - docs/architecture/components/frontend.md
  - docs/architecture/decisions/adr-010-frontend-stack.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-49-ai-service-pipeline-trace.md
---

# TICKET V2-50: Design refresh and Pipeline Inspector UI

> **Scope:** `web` | **Size:** `L` | **Priority:** `P1`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP`

> **Recorded after the work was done.** The code was written by another agent session on the working tree without a ticket. This file records what is in the code, the evidence the orchestrator saw on 2026-11-24, and what nobody has checked. The real size is XL (about 120 files); it is recorded as `L` only because the plan check rejects an unsplit XL ticket, and splitting a finished change into two tickets would not make it easier to review. It is not an owner-reviewed design, and no `frontend-delivery` milestone or owner design review was recorded for it.

## 1. Context & goal
Refresh the whole UI for the acceptance demo (light and dark themes, a calmer visual system) and show how a question travels through the pipeline (the Pipeline Inspector, fed by the `step` events and the trace route of [V2-49](V2-49-ai-service-pipeline-trace.md)).

## 2. What the code does
- **Design system.** All CSS-module primitives in `components/ui/*` (26 files removed, `Breadcrumb` dropped) are rebuilt as Tailwind 4 components with `class-variance-authority`, `tailwind-merge` (`lib/utils.ts` `cn`) and a few Radix primitives (dialog, popover, switch, tooltip, checkbox, scroll-area, slot). Tokens stay in `app/globals.css`; the fonts are Plus Jakarta Sans and JetBrains Mono through `next/font/google` (`latin`, `vietnamese`).
- **Theme.** `next-themes` with a `ThemeProvider`; the preference key is `sopilot-theme` (never a token). Light and dark, collapsible sidebar, `sonner` toasts, `cmdk` command palette (`Ctrl+K`), `motion` animations with `reducedMotion="user"`, and decorative effects (`components/effects`, `components/motion`).
- **Screens.** Login, invite, chat, documents, document detail, members, departments, knowledge gaps, audit, settings and workspaces were restyled; the processing report and the citation viewer follow the new tokens. No API call changed.
- **Pipeline Inspector.** `components/chat/inspector/*` (panel, stage cards, detail modal), `store/inspector-store.ts`, `lib/chat/pipeline-trace.ts` (+ tests) and `lib/chat/citation-groups.ts`. `lib/sse/stream.ts` always sends `includeTrace: true`; `lib/sse/parser.ts` decodes the `step` event; `getMessageTrace` loads a stored trace.
- **Proxy.** `next.config.ts` raises `proxyTimeout` from 120 s to 600 s so a Modal cold start does not cut the stream.
- **Docs.** `docs/architecture/components/frontend.md` describes the new visual direction and styling system (it said light mode only and frozen CSS modules).

## 3. Dependencies added (CLAUDE.md constraint 12: owner to confirm)
13 npm packages: `@radix-ui/react-{checkbox,dialog,popover,scroll-area,slot,switch,tooltip}`, `class-variance-authority`, `cmdk`, `motion`, `next-themes`, `sonner`, `tailwind-merge`. `pnpm-lock.yaml` changed with them.

## 4. Evidence (output seen by the orchestrator, 2026-11-24)
- `./scripts/validate-build.ps1 -Scope web` on this layer (without the V2-48 toggle): build, lint and 247 Vitest tests passed (18 files).

## 5. Not verified
- No owner design review and no `frontend-delivery` acceptance for the refresh; the screens were not compared with any approved comp.
- The Pipeline Inspector and the new components were not opened in a browser by the orchestrator in this session (the owner did use the chat page).
- `tests/e2e` (Playwright, uncommitted and not part of this change) was not run against the new markup; selectors may have changed.
- Accessibility (contrast of the dark theme, focus order of the command palette and dialogs) and the 390 px layout were not checked.
- `.claude/rules/frontend.md` still says the CSS-module primitives are frozen; it is an agent rule file and was not edited here.

## 6. Results
Review-ready on the working tree, 2026-11-24. Docs updated: `docs/architecture/components/frontend.md`.
