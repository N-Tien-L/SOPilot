---
title: "Frontend constraints and non-functional requirements (input to the stack decision)"
status: approved
created: 2026-11-14
updated: 2026-11-14
author: "Owner"
affected_services: [web]
affected_schemas: []
refs:
  - docs/architecture/components/frontend-feature-inventory.md
  - docs/architecture/components/frontend.md
  - docs/architecture/api/http-conventions.md
  - docs/architecture/domain/identity-and-access.md
  - docs/product/prd-v2-sopilot-mvp.md
  - .claude/rules/frontend.md
---

# Frontend constraints and non-functional requirements

> **Status:** approved (owner, 2026-11-14), step 2 of the frontend stack decision (inventory → **NFRs and constraints** → options and ADR → V2-15). Derived from [the feature inventory](frontend-feature-inventory.md). Section 1 is fixed by existing docs, code and owner decisions and is not up for debate in the stack decision. Section 2 mixes requirements taken from existing docs (**source** column names them) with ones marked **proposed**; the owner accepted every proposed item as written on 2026-11-14 (section 5). The **proposed** tag stays only to show where a requirement did not already exist in another document.

## 1. Constraints (fixed)

| ID | Constraint | Source |
|---|---|---|
| C1 | Local only, run with `docker compose` or from source; no public deployment. SEO, edge caching and server-rendered public pages are not needed. | ADR-006, PRD §8.2 |
| C2 | Two backends behind one origin with different conventions: core-api (`/api/v1`, envelope `{data, traceId}`, errors `{error:{code,message,details}}`) and ai-service (`/ai/v1`, plain JSON, errors `{detail}` with no code; only the SSE `error` event carries a code). | [http-conventions](../api/http-conventions.md) §2, §3 |
| C3 | Answers stream as `text/event-stream` over `POST` with a Bearer header (events `meta`, `delta`, `replace`, `refusal`, `citations`, `done`, `error`). The browser `EventSource` API cannot send a body or a header, so streaming needs `fetch` and a stream reader. | http-conventions §3, TECH-V2-ai-service §7.2 |
| C4 | The refresh token is an `HttpOnly; SameSite=Strict` cookie scoped to `/api/v1/auth`, so the browser must reach the API on the **same origin** as the page (a proxy or rewrite is required in dev and in compose). The access token (≤ 15 min) lives in memory. | [frontend.md §3](frontend.md), identity-and-access |
| C5 | Refresh rotation is strict: two tabs refreshing with the same cookie count as reuse and revoke the session. Refreshes must be merged into one request across tabs. | V2-29 review note |
| C6 | Tokens are per workspace (`wid`, `wrole`, `wdept`); switching workspace reissues the token (`POST /auth/switch-workspace`). | V2-15, http-conventions §2 |
| C7 | The server is the authority: another workspace's or an unreadable object is `404`; the UI only hides what a role cannot do. | PRD FR-19, FR-25 |
| C8 | Markdown from documents and model output renders without raw HTML (`rehype-raw` removed); external images become links. | V2-32 |
| C9 | UI copy, code, comments and docs are all English (owner decision 2026-11-14, section 5). Document content and questions remain multilingual (Vietnamese and English). | section 5 |
| C10 | No new dependency, framework or tool without stating why and getting agreement. There is no test runner in `frontend/web` today; one is approved in principle (section 5) but arrives through a ticket. | CLAUDE.md #12, `.claude/rules/frontend.md` |
| C11 | Gates are `pnpm build` (strict type-check) and `pnpm lint`; 61 lint errors exist today and V2-38 clears them. | V2-38 |
| C12 | UI tickets need browser evidence per acceptance criterion, including a narrow screen. Supported browsers: Chrome and Firefox first (section 5). | V2-15, V2-32 |
| C13 | The frontend must run both in compose and with `pnpm dev` on the host; backend targets come from server-side env (`CORE_API_URL`, `AI_SERVICE_URL`). | V2-15 §3 |
| C14 | V2-31, V2-32 and V2-33 are blocked on V2-15 and use its shell. | PLAN |

## 2. Non-functional requirements

### Security
| ID | Requirement | Source | How verified |
|---|---|---|---|
| S1 | No access or refresh token in `localStorage`, `sessionStorage`, URLs or logs. | frontend.md §3, FR rules | code review, grep |
| S2 | A Markdown fixture with `<script>`, `<img onerror>` and an external image runs no script and loads no external resource. | V2-32 | browser |
| S3 | No document text, tokens or `X-Internal-Token` in client logs or error reports; no new `console.log`. | CLAUDE.md #6, #7 | lint, review |
| S4 | Error text shown to users is the API's fixed message or a local fixed string, never a raw exception. | CLAUDE.md #6 | review |
| S5 | Hidden controls are never the only protection (C7); tests cover the 404 and 403 paths the UI must show. | PRD FR-25 | browser |

### Reliability and correctness of the hard interactions
| ID | Requirement | Source | How verified |
|---|---|---|---|
| R1 | Concurrent refreshes from several tabs produce one request and never log the user out. | V2-29 note | manual two-tab test |
| R2 | Upload: at most 10 files per batch, at most 3 in flight, each file has its own state and retry; a failed file never blocks others; closing the dialog does not cancel in-flight uploads. | V2-31 | browser |
| R3 | Status polling runs only while some document is processing and stops otherwise; it does not leak across navigation or workspace switch. | V2-31 | browser |
| R4 | A stream that errors, is cancelled by the user, or loses the network ends in a defined state (partial answer kept or marked, retry offered); `replace` and `refusal` events override streamed text correctly. | proposed | manual, fixtures |
| R5 | Citation highlighting uses UTF-16 offsets on the canonical Markdown only and is correct with emoji; the original PDF opens at `#page=N` in the browser's native viewer (on demand), with no PDF library; an old-version citation never opens the viewer. | V2-15, V2-32, owner decision | browser |
| R6 | History entries with `hidden: true` render a note instead of content. | http-conventions §3 | browser |
| R7 | Switching workspace clears all cached server state of the previous workspace (queries, stores, open streams). | proposed (tenant safety) | manual |

### Performance (local stack; numbers proposed, to be calibrated)
| ID | Requirement | Source |
|---|---|---|
| P1 | Deltas render as they arrive: the frontend adds no buffering that delays the backend's first-token target (P95 < 3 s). | PRD §4, proposed |
| P2 | Opening a citation shows the cited passage promptly after the content response; no numeric budget yet. | proposed |
| P3 | Typing and scrolling in chat stay smooth while a long answer streams (no per-token full-list re-render). | proposed |
| P4 | Navigation between shell screens feels immediate on cached data. | proposed |

No bundle-size or Lighthouse budget is proposed: the app is local-only (C1) and a baseline does not exist yet.

### Usability and accessibility
| ID | Requirement | Source |
|---|---|---|
| U1 | The viewer and upload flows work on a narrow screen (viewer uses two tabs). | V2-31, V2-32 |
| U2 | English UI copy; inputs, search and the Markdown view handle Vietnamese diacritics correctly. | C9 |
| U3 | Keyboard operability and visible focus on all interactive controls (required); WCAG 2.1 AA is the reference, followed flexibly rather than strictly (owner decision 2026-11-14). | owner decision |
| U4 | Loading, empty, error and processing states exist for every list and flow (documents, members, gaps, history). | proposed |

### Maintainability and testability
| ID | Requirement | Source |
|---|---|---|
| M1 | One typed API client covers both backends and both error conventions; the exceptions listed in `.claude/rules/frontend.md` (second axios client, direct `fetch`) are removed. | rules/frontend.md |
| M2 | Types for each contract are declared once and shared. | rules/frontend.md |
| M3 | Dependencies used only by cut V1 features (`recharts`, `mammoth`, `sass`, `rehype-raw`, the legacy `react-query` v3 package) leave with the code, or are justified. | V2-15, C10 |
| M4 | The risky logic is covered by unit tests: refresh single-flight, upload queue state machine, SSE event parsing, UTF-16 range mapping. | owner decision (runner chosen in the ADR, added by a ticket) |
| M5 | The codebase stays workable for one or two people: few concepts, no parallel patterns for the same job (one data-fetching approach, one state approach). | PRD §1 |

### Operability
| ID | Requirement | Source |
|---|---|---|
| O1 | One `docker compose up` brings the UI up beside the backend. | PRD §4 reproducibility |
| O2 | Error screens surface the `traceId` (core-api) so a failure can be matched to a server log. | proposed |

## 3. Priorities (proposed)

When requirements pull against each other, decide in this order:

1. **Security and tenant safety** (S1 to S5, R1, R7): a leak or a lost session breaks the research claim.
2. **Correctness of the hard interactions** (R2 to R6): streaming, viewer, upload.
3. **Maintainability and delivery** (M1 to M5): four L tickets are queued behind V2-15.
4. **Testability** (M4).
5. **Performance** (P1 to P4): local only.
6. **Visual polish**: a later pass (agreed 2026-11-14).

## 4. What this means for the options

Any option, including keeping the current stack, must provide:

- a same-origin proxy to both backends in dev and compose (C4, C13);
- `fetch`-based streaming with a hand-written or small SSE parser (C3);
- cross-tab coordination for refresh (Web Locks or `BroadcastChannel`; C5);
- safe Markdown rendering and a PDF display path (C8, V2-32);
- a unit test runner for pure logic (M4), chosen in the ADR; and no PDF library (R5).

None of these requires server rendering (C1), so the stack question is mostly about the data layer, the routing and proxy setup, the amount of V1 code carried over, and delivery cost, not about rendering strategy.

## 5. Owner decisions 2026-11-14

| Topic | Decision | Effect here |
|---|---|---|
| UI language | The UI is **English** (changes the earlier Vietnamese UI rule). Users still ask and upload in Vietnamese or English; answers follow the question's language. | C9, U2 |
| Test runner | Yes, a unit test runner is allowed for M4. The tool is chosen in the stack ADR and introduced by a ticket. | C10, M4 |
| Accessibility | Keyboard operability is required; WCAG 2.1 AA is the reference, followed flexibly, not strictly. | U3 |
| Browsers | Narrow support first: Chrome and Firefox; widen later. | C12 |
| PDF display | The browser's native PDF viewer opening at `#page=N` is enough; no PDF library. Highlighting happens only on the canonical Markdown view. The original PDF opens at the page, or loads on demand when the user asks for the source file. | R5, V2-32 |
| Performance | Qualitative for now (P1 to P4); no numeric budgets until a baseline exists. | P2 |
| Dark mode and theming | Deferred to the polish phase. | out of scope |
| Proposed items | All accepted as written (R4, R7, P1 to P4, U4, O2, the section 3 priorities and the other items tagged proposed). | section 2, 3 |
