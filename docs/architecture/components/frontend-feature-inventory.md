---
title: "Frontend feature and interaction inventory (input to the stack decision)"
status: approved
created: 2026-11-14
updated: 2026-11-14
author: "Owner"
affected_services: [web]
affected_schemas: []
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/components/frontend.md
  - docs/architecture/decisions/adr-009-department-publishers.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-15-frontend-trim-and-citations.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-31-frontend-document-upload.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-32-frontend-source-viewer.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-33-frontend-member-metadata-admin.md
---

# Frontend feature and interaction inventory

> **Status:** approved (owner, 2026-11-14), step 1 of the frontend stack decision (inventory → NFRs and constraints → options and ADR-010 → V2-38 → V2-15). It lists what the UI must do and which parts of that put real demands on the stack. It does not repeat requirements: FR/UC ids link to [PRD-V2](../../product/prd-v2-sopilot-mvp.md), which stays the source of truth. Built from the PRD and tickets V2-15, V2-31, V2-32, V2-33 on 2026-11-14; nothing here was checked against the running app.

## 1. What the app is, for the frontend

A multi-tenant web app where people sign in with Google, work inside one workspace at a time, upload PDF/Markdown SOPs, and ask questions answered with streamed, cited text. Users are logged in and work from the local stack; there is no public site (ADR-006). The UI, code and docs are English (owner decision 2026-11-14); documents and questions stay multilingual.

Two product surfaces:

- **Ask**: chat with streaming answers, citations, refusals, and a viewer that opens the cited passage.
- **Manage**: documents (upload, status, metadata, visibility), members, departments, invitations, knowledge gaps, workspace settings.

## 2. Roles and what changes in the UI

Roles come from token claims (`wid`, `wrole`, `wdept`). The UI hides what a role cannot do; the server decides (PRD FR-25, [frontend.md §3](frontend.md)).

| Capability | MEMBER | ADMIN | OWNER | Publisher (per scope) | Source |
|---|:---:|:---:|:---:|:---:|---|
| Chat, view and download readable documents | yes | yes | yes | yes | FR-11, FR-25 |
| Upload, replace, delete, edit metadata | no | no | revoke any | own scope only | FR-06, FR-26, ADR-009 |
| Change visibility between workspace and departments | no | no | yes | list of readers, own department | FR-25 |
| Invite, change role, suspend members | no | yes (not OWNER actions) | yes | no | FR-04, FR-22 |
| Departments, categories | no | yes | yes | no | FR-23, FR-27 |
| Knowledge-gap list | no | yes | yes | no | FR-17 |
| Audit log | no | no | yes | no | FR-20 |
| Assign publishers | no | no | yes | no | ADR-009 |

A solo user (personal workspace) sees none of the department or profile UI (FR-22, V2-33).

## 3. Screens

| Screen | Requirements | Ticket | Main interactions |
|---|---|---|---|
| Sign-in | FR-01, UC-01 | V2-15 | Google sign-in, session start |
| Workspace picker and switcher | FR-02, FR-03 | V2-15 | list, switch, create; tokens kept per workspace |
| Shell and navigation | PRD §5 UI row | V2-15 | chat, documents, members and invitations, gaps, settings |
| Chat | FR-10 to FR-13, FR-15, FR-16 | V2-15 | SSE answer, `[n]` citations, refusal by reason, warnings, answer feedback, conversation list with rename and delete |
| Citation viewer | FR-14 | V2-32 | open page or passage, highlight by UTF-16 offset |
| Recognized-content view | FR-31 | V2-32 | PDF beside canonical Markdown, page jump, version label, warnings |
| Document list | FR-07, FR-26, FR-27 | V2-15, V2-31 | status, filters, polling while processing |
| Upload dialog | FR-30, UC-12 | V2-31 | up to 10 files, 3 concurrent, per-file status and retry, error variants |
| Document metadata and visibility | FR-26 to FR-28, UC-09 | V2-33 | edit, suggestion form, scope selection |
| Members, departments, invitations | FR-04, FR-22, FR-23, UC-02, UC-07, UC-08 | V2-33 | profile edit, suspend, invitation links |
| Knowledge gaps | FR-17, UC-05 | V2-15 | list, mark handled |
| Workspace settings | FR-03 | V2-15 | create, rename, delete (delete OWNER-only) |
| Publisher assignment | ADR-009 | V2-33 | OWNER assigns workspace and department publishers |
| Audit log | FR-20 | V2-33 | OWNER-only read-only list |

## 4. Interactions that put demands on the stack

Most screens are forms and lists. These are the ones that are not, and so drive the decision:

1. **Streaming answers over SSE.** Tokens arrive incrementally, citations must be mapped and unmappable ones are removed server-side; the UI must handle refusal, warnings and `done` events mid-stream (TECH-V2-ai-service §7.2).
2. **Document viewer with highlighting.** Canonical Markdown rendered safely (no raw HTML) with highlighting by UTF-16 offsets (emoji must work); the original PDF opens in the browser's native viewer at the cited page, on demand (owner decision 2026-11-14); two tabs on narrow screens. One component shared by the citation viewer and the recognized-content view (FR-14, FR-31).
3. **Upload queue.** Per-file state machine (uploading, processing, ready, failed), concurrency cap of 3, independent retry, dialog may close mid-batch, leave-page warning only while bytes are sent.
4. **Status polling.** Document lists refresh while anything is processing and stop when nothing is.
5. **Auth and session.** Refresh token in an `HttpOnly` cookie, access token in memory, per-workspace tokens, refresh merged across tabs because rotation treats a second refresh as reuse ([frontend.md §3](frontend.md)).
6. **Role- and scope-dependent UI.** Visibility rules by role, department and publisher status, with server errors shown in context.
7. **Typed contracts with two backends.** core-api (`/api/v1`, envelope `{data, traceId}`) and ai-service (`/ai/v1`, plain JSON and SSE) behind one origin (`http-conventions.md`).
8. **Narrow screens and Vietnamese text.** The UI copy is English, but inputs, search and the Markdown view must handle Vietnamese diacritics; the viewer and upload flows have explicit narrow-screen requirements.

Not drivers: SEO, public caching, server-rendered marketing pages, offline use, real-time collaboration, large lists (quota caps a workspace at 50 documents by default, FR-09).

## 5. Out of scope in V2 (do not design for)

System admin pages, analytics and exports, passwords and OTP, session management, department trees, OnlyOffice and version comparison, a Markdown editor, a model picker, ZIP or folder import, DOCX, public deployment (PRD §5, §8).

## 6. Scope gaps and how they were resolved

Checked against the acceptance criteria of V2-15, V2-31, V2-32, V2-33 and the backend tickets on 2026-11-14. Owner decisions of the same day are recorded in the V2 PLAN decision notes (§5).

| Requirement | Resolution |
|---|---|
| Conversation list, rename, delete (FR-15), answer feedback (FR-16) | Added to V2-15 |
| Workspace create, rename, delete (FR-03) | Added to V2-15 (settings screen) |
| Publisher assignment (ADR-009), audit log view (FR-20) | Added to V2-33 (OWNER-only) |
| Invitation acceptance for the invitee (UC-02, UC-07) | Already in V2-33 ("create/revoke/accept invitation links"); not a gap |
| Domain join (FR-05, UC-03), CSV member import (FR-24) | P1; no frontend in the MVP |

## 7. Next

Done: [NFRs and constraints](frontend-nfrs.md) and [ADR-010](../decisions/adr-010-frontend-stack.md). Next: V2-38 (foundation), then V2-15.
