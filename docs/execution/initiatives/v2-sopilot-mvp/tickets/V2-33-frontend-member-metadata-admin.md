---
id: V2-33
title: "Frontend: members, departments and document metadata"
type: feat
status: review
created: 2026-10-24
updated: 2026-11-16
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-15, V2-23, V2-24, V2-25, V2-30, V2-36]
blocks: [V2-17]
branch: "feat/web-v2-33"
assignee: pair
---

# TICKET V2-33: Frontend: members, departments and document metadata

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
Scope split from V2-15 (XL) on 2026-10-24; the approved PRD/TECH requirements are unchanged. Use the frontend-delivery skill and `.claude/rules/frontend.md` when implementing. FR-04/FR-22 to FR-29.

## 2. Acceptance criteria
- [x] Members: profile (full name, employee code, job title, department), suspend/unsuspend; flat departments and categories: create, rename, archive, delete when allowed. Hide departments in a single-member workspace.
- [x] Documents: edit metadata, choose the `WORKSPACE`/`DEPARTMENTS` scope, view and accept/edit metadata suggestions; the suggestion status does not block other actions.
  - The suggestion form follows the owner decision of 2026-11-12 in V2-25 §2a: one editable form, `doc_code`/revision/effective date read-only, the create-suggested-category button only for OWNER/ADMIN.
- [x] UI to create/revoke/accept invitation links; OWNER/ADMIN actions by permission, with API errors shown in context.
- [x] Changed 2026-11-14 (owner decision, frontend inventory gaps): OWNER-only screen to assign and change the workspace publisher and each department's publisher (ADR-009, API in V2-36), and an OWNER-only audit log view (`GET /audit-logs`, FR-20).
- [x] Browser check of admin/member permissions, suspended status, suggestions running/failed, changed read access, publisher assignment and the audit log view.

## 3. Guide
1. Declare types in `frontend/web/types` and the endpoint calls on the V2-38 API client (`frontend/web/lib/`) per TECH-V2-core-api/ai-service.
2. Implement in `frontend/web/app/` and `frontend/web/components/`, using the V2-15 shell.
3. Record browser evidence per acceptance criterion; update the frontend README.
- Update the related contracts in `docs/architecture/` along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Browser: profiles/departments/flat categories, invitations, last OWNER, editing document access, metadata suggestions not blocking upload/chat.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit.

## 5. Progress notes and evidence (2026-11-16, `review`)

Branch `feat/web-v2-33`, from `develop` after V2-31 and V2-32 were fast-forwarded into the local `develop` (`0b5f1ec`, not pushed). Not committed.

**Built:** `/members` tabs (members, invitations, departments, categories, OWNER-only publishers), OWNER-only `/audit`, public `/invite`, the header badge for the account's pending invitations, and the document details dialog (metadata form with suggestions, access section) opened from `/documents` and `/documents/[id]`. Pure rules with Vitest in `lib/admin/` (`metadata.ts`, `members.ts`, `audit.ts`, `invite.ts`: 32 tests); typed calls and workspace-keyed hooks added to `lib/api/endpoints.ts` and `lib/query/hooks.ts`. No dependency added, no backend change. Documents: [frontend.md](../../../../architecture/components/frontend.md) section 4 and the web README.

**Endpoint gap report (before building; none blocked the ticket):** every call the ticket cites exists (members, departments, categories, tags, document `PATCH`/`PUT /visibility`/`PUT /ownership`, invitations, publishers, audit logs). Suggestions need no new endpoint: `DocumentView.fieldSources` and `suggestions` are returned for OWNER/ADMIN and the responsible publisher. Gaps left open: (1) the invitation link is `/invite#token=...` and the app had no such route (added here); (2) no list of documents with an unapplied `proposedCategoryName` and no bulk category assignment (already deferred in V2-25 section 2a); (3) document code, revision and effective date are read-only for lack of a version-level endpoint (owner decision 2026-11-12).

**Decisions and deviations**
- The ticket says "choose the `WORKSPACE`/`DEPARTMENTS` scope". ADR-009 decision 8 lets only an OWNER switch the scope or the owning department, so the dialog calls `PUT /ownership` for an OWNER and shows the reason (button disabled) to everyone else; a publisher still edits the reader departments in the same scope with `PUT /visibility`. This was found by the real `409 OWNERSHIP_CHANGE_REQUIRES_OWNER` in the first browser run, then built as `planAccess` with tests.
- Remove member, rename/archive/delete of categories and departments and the "Use suggested title" button are included (the ticket lists them as "when allowed" or implies them); the role field in the member form is included because a role change is how an owner makes an admin.
- The `sr-only` header cell in a scrolling table made the whole page scroll sideways at 375 px; the wrappers got `relative` (this includes the V2-31 documents table, which is touched here).

**Verification**
- `./scripts/validate-build.ps1 -Scope web`: build, lint and Vitest pass (202 tests in 15 files).
- Real stack (compose Postgres, MinIO, core-api, ai-service, ai-worker; `pnpm dev` from source on `http://localhost:3000` with the compose `web` container stopped for the run and started again; `playwright-core` already on the machine, scripts in the session scratchpad, nothing added to the repo): Chromium 159 and Firefox 159, **74 of 74 checks each** in the last run, after fixing the findings below. A fresh team workspace, owner, member, third member and an invited account per run. Pages opened: `/login`, `/chat`, `/members` (all five tabs), `/invite` (signed out, signed in, pending by id), `/documents`, the details dialog, `/audit`, and `/members`, `/audit` as a plain member and as an admin.
- Covered with real calls: single-member workspace without the Departments tab or column; categories (create, duplicate refused, rename, archive, restore, delete); invitation (link shown once, duplicate email refused, revoke, revoked link refused, accept through the link after signing in, accept a pending invitation from the header badge); member profile (name, employee code, job title, department), duplicate employee code refused, suspend (the member is signed out) and reactivate, role to ADMIN (admin sees no Publishers tab or Audit log and no action on the owner row) and back, last owner demotion refused, remove member (the member is signed out); publishers (workspace and department assigned, department publisher removed); a real upload reaching `READY` with the real worker and real suggestions (source labels, "Suggestions to review" badge, validation of description and tags, empty title kept, tags de-duplicated, category and tags saved); access: a workspace publisher's scope switch is explained and disabled, the OWNER transfers to Operations (the third member loses the document, the Operations member keeps it, the previous publisher loses Edit), a department publisher adds a reader department with `PUT /visibility` and cannot switch to the whole workspace, the OWNER moves it back (the third member sees it again); audit log (32 entries, filters by action and actor, no token or link in the page); keyboard (focus enters the dialog, Escape closes it); 375 px (members and documents pages without sideways scroll, the dialog fits).
- Mock-assisted (`page.route`, labelled in the script output): the FAILED state of a document in the dialog ("Processing failed, so no suggestions were made"), because a real FAILED row cannot be produced (below); and a suggested title and a proposed new category, because the real suggestions proposed neither (plain publisher sees the proposed category as text with no button; the OWNER's "Create suggested category" button did a real `POST /categories` and selected it).
- Screenshots (local, git-ignored): `docs/quality/evidence/v2-33/` (Chromium and Firefox).

**Findings fixed during the browser runs:** the invitation token stayed in the address bar (the router re-applies the URL after a render-time strip; now removed in an effect); plain members triggered `403 GET /members` from `/members` and from the dialog (the query is now enabled for OWNER/ADMIN only); reordering tags alone sent a no-op `PATCH` (tags compare as a set); the sideways scroll above.

**Found outside this ticket:** the worker marked a corrupt PDF `ingest_failed` (`CORRUPT_FILE`) but the version stayed `PROCESSING` in core-api (the `FAILED` callback was accepted but a late `PROCESSING` event overrode it, because the two outbox events are delivered out of order; fixed by [V2-41](V2-41-core-api-version-status-callback-order.md)), so the "suggestions failed" path could not be exercised with a real FAILED document. One of three Chromium runs lost the member's session on a page reload (strict refresh rotation, the case [V2-39](V2-39-core-api-refresh-grace-window.md) addresses; the script signs in again and counts it; Firefox had none); not investigated further.

**Review (fresh `v2-reviewer`, claude-opus-5-5, one round):** one blocker and two warnings fixed, notes handled as below. The reviewer ran no build, test or browser, so the gate was re-run by me.
- BLOCKER, Edit gated on `fieldSources` although only the responsible publisher may write (`DocumentWritePolicy`; ADMIN and OWNER roles grant no write): fixed. `canWriteDocument` and `canEditDetails` in `lib/admin/metadata.ts` gate the Edit buttons (publisher, or OWNER for transfer; never ADMIN alone); the dialog disables the details form for a non-publisher and says why.
- WARNING, `planAccess` sent a same-scope reader change by an OWNER who is not the publisher to `PUT /visibility` (403): it now plans a transfer with the owner department unchanged, and blocks an ADMIN. Tests added.
- WARNING, the publishers panel offered every member for every department (409 `PUBLISHER_NOT_IN_DEPARTMENT`): candidates are filtered by department.
- NOTES fixed: six missing audit action codes added; the held invite token is also cleared when a local session ends; README corrected (own row offers Edit only, Edit gating); publishers copy corrected; a literal NUL character in `metadata.ts` replaced by an escape.
- NOTE left open: after a successful access save the dialog compares against the list snapshot, so reverting to the original selection needs a reopen.
- One of my own fixes was wrong and was caught by the Google run: clearing the held invite token inside `endLocalSession` also ran when a signed-out page tried to restore a session, so the token was lost before sign-in. It is now cleared only by an explicit sign-out.
- Re-verification after the fixes (2026-11-16, real core-api, ai-service and worker; web from source): the full run again in Chromium 159 and Firefox 159, 74 of 74 each, 0 session losses. Its OWNER-side suggestion step was adapted: the form is now editable only for the responsible publisher, so the script makes the OWNER the workspace publisher first. New fix-path run `fixes.cjs`, 20 of 20 in both browsers: ADMIN, a publisher of another department and a non-reader get no Edit; the department publisher edits (PATCH 200); an OWNER who is not that publisher sees the form disabled with the explanation and changes readers through `PUT /ownership` (200, no `/visibility` call); the API refuses an ADMIN `PUT /visibility` (403); the publisher picker lists only that department's members; the audit filter has the added codes; an archived department is not offered as a reader; an invitation opened by an account with another email is refused with the fixed message.
- Google sign-in, in the owner's own Chrome (client id supplied by the owner, `http://localhost:3000` an authorized origin): sign-in lands in the workspace; a reload keeps the session; `/members` (tabs), `/audit` and `/documents` open for that OWNER with no failed requests; an invitation to that Google email, opened by link while signed in, is accepted and the account becomes MEMBER (Members nav hidden); signed out, the link asks to sign in, Google sign-in returns to `/invite` with the token intact and the invitation is accepted. The account chooser popup needed a human click, so this part was run with the owner.

**Second verification round (2026-11-16, owner asked for the open items):**
- Browsers: the full 74-check run passes in Chromium, Firefox, Edge (the installed Microsoft Edge, Chromium engine) and Playwright's WebKit (the Safari engine, not Safari itself), 74 of 74 each, and the fix-path run 20 of 20 in each of them. All of them ran on the final code, after the two a11y fixes below.
- Found and fixed: (1) the `/members` tabs ignored the arrow keys; they now follow the WAI-ARIA tabs pattern (roving tab index, arrows, Home, End). (2) For an OWNER who is not the document's publisher the dialog opened with focus left on the page behind it: the frozen `Modal` picks the first element matching its focusable selector, which includes fields inside the disabled fieldset that cannot take focus; the explanatory note is now focusable and is where focus lands.
- Found, outside this ticket: WebKit never sends the `Secure` `sp_refresh` cookie over `http://localhost`, so on Safari every reload ends the session in local development (Chromium and Firefox treat localhost as secure). WebKit was run with core-api temporarily started with `SOPILOT_AUTH_COOKIESECURE=false` through an override file kept outside the repo, then restored. Needs an owner decision (local HTTP dev setting or a note in the local-development guide); no ticket opened.
- Department publisher: uploads straight into a department scope (`visibility=DEPARTMENTS`, owner department set; 201), is refused a workspace-scoped upload (`403 NOT_PUBLISHER`), sees and edits that document in the UI; a member outside the department does not see it.
- FAILED: a corrupt PDF accepted by the API (201) stays `PROCESSING` after two minutes, which is the V2-41 behaviour (a late `PROCESSING` callback overrides `FAILED`; fixed in V2-41), so a real FAILED row still cannot be produced here. That dialog state stays mock-assisted.
- Keyboard and accessibility (Chromium, 20 of 20): Enter on Edit opens the dialog with focus inside; 55 Tab and Shift+Tab presses never leave it; Escape closes it and focus returns to the Edit button; the Remove confirmation opens with focus inside and Escape cancels it; arrows move across the tabs; every control in the dialog and on the five `/members` tabs and `/audit` has an accessible name; the dialog is `aria-modal` and named; the accessibility tree exposes the form, the radio group and the buttons. This is the accessibility tree and keyboard behaviour, **not** a run with a real screen reader (NVDA, Narrator, VoiceOver), which an agent cannot drive.
**Not verified:** Safari itself (only its engine, WebKit, ran), a real FAILED document, a real screen reader (NVDA, Narrator, VoiceOver), and visual acceptance (the owner judges the look; the screens use the existing "Ink & Teal" tokens and the frozen UI primitives). The same tablist keyboard gap exists on `/gaps` (not changed here).
