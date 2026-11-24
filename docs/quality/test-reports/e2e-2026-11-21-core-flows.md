---
id: TEST-REPORT-004
title: "E2E walkthrough: audit log, workspace, invitations, auth, uploads and failure states, 2026-11-21"
status: draft
created: 2026-11-21
updated: 2026-11-21
author: "Owner"
verdict: PASSED_AFTER_FIXES
refs:
  - docs/quality/test-plans/test-plan-001-e2e-business-flows.md
---

# TEST-REPORT-004: E2E walkthrough, features that need no LLM

## 1. Verdict

One real application bug (B1) and four UI/wording findings. No tenant or permission rule was broken.

- Commit `6f8bf49` plus uncommitted changes. core-api was rebuilt from the working tree (includes the department validation fix from TEST-REPORT-003); web and ai-service were up. For the failure-state test I stopped `ai-service` and `ai-worker` (containers I had started) and started them again afterwards.
- Chat and answer quality were not run (they call the LLM provider).

## 2. What was run

| Run | Result |
|---|---|
| Suite 01 to 05 (`./scripts/run-e2e.ps1 -Keep`) | 40 passed |
| `tests/tenant-isolation` (`uv run pytest -q`) | 31 passed |
| 47 HTTP checks: audit, workspace, invitations, members, auth (script, not committed) | 43 passed, 4 failed (B1 and three wrong expectations of mine, see below) |
| About 20 malformed-input probes (bad UUID, date, number) | 12 returned `500` (B1) |
| 25 HTTP checks: document upload, versions, download, delete | 22 passed, 3 failed (all wrong expectations of mine) |
| Browser: audit log, settings, knowledge gaps (phone), dialog keyboard test, tablet overflow, ai-service down | findings U1 to U4 |

What held up: the audit log is owner-only, filters by action, never contains tokens or secrets, and records department, category, document, invitation and publisher changes. Admin and member get `403` on the audit log, workspace rename and delete. Blank or 300-character names are refused. A personal workspace cannot be deleted or left; the last owner cannot leave or be demoted; an admin cannot demote or suspend an owner. Invitations: duplicate, bad email, bad role and `OWNER` are refused; the list never shows the link; revoke then accept is `410`; accepting as the wrong account is refused; a suspended member cannot switch workspace. Uploads: duplicate bytes `409`, `.exe` `415`, invalid UTF-8 `415 INVALID_ENCODING`, 21 MB `413`, empty file `400`, four concurrent identical uploads give exactly one `201`, a new version supersedes the old, `download-url` returns the same bytes, a plain member cannot upload or delete, the owner can delete (recall) as designed. The delete-workspace dialog needs the workspace name typed, traps focus, closes with Escape and returns focus. No horizontal overflow on any screen at 768 px.

Checks that first showed FAIL but are not bugs: accept-by-id as another account returns `404` (hides the invitation); revoking twice is `204` (documented idempotent); accepting the same invitation twice as the same user is a documented no-op; an empty-looking "invalid UTF-8" file that contained a NUL byte is `UNSUPPORTED_TYPE` (correct).

## 3. Findings

### B1. Malformed query or path values return 500 instead of 400 (app bug, medium)

`MethodArgumentTypeMismatchException` is not handled in `GlobalExceptionHandler`, so any value that cannot be converted ends as `500 INTERNAL_ERROR` and an `ERROR` log line. Steps (as owner): `GET /audit-logs?from=notadate`, `?to=2026-99-99`, `?actorId=notuuid`; `GET /documents?categoryId=notuuid`, `?ownerDepartmentId=notuuid`, `?limit=abc`, `GET /documents/notuuid`, `GET /documents/notuuid/download-url`; `PATCH /members/notuuid`; `DELETE /departments|categories|invitations/notuuid`; `PUT /departments/notuuid/publisher`. Expected: `400 VALIDATION_FAILED`. Not a leak (the body is the fixed `INTERNAL_ERROR` text), but a client mistake should not look like a server fault.

### U1. Audit log table hides Action and Details on a phone

At 375 px only When and Actor are visible; Action and Details need a sideways scroll with no hint. The Members table had the same problem and was fixed with cards (TEST-REPORT-002 F1). At 1024 px the Details column is also clipped inside its own scroll area.

### U2. Failure messages for documents are Vietnamese

`services/core-api/.../document/FailureMessages.java` returns Vietnamese sentences (for example "Tệp bị hỏng hoặc không đọc được...") that the UI shows on a failed document. UI copy is meant to be English (owner decision 2026-11-14). Not run through a real failure here (no corrupt PDF case).

### U3. With ai-service down, the error appears only after about 25 seconds and offers no retry

Corrected on re-check: the screens do show "Something went wrong. Please try again." but only after about 25 s (the proxy takes 5 s to fail, three attempts), with a grey skeleton and "Loading..." until then, and no way to retry. The proxy answers a plain-text `500` (a `502` or `503` would describe it better).

### U4. Minor

- An upload without `visibility` is accepted and defaults to the workspace; a file name such as `../../etc/passwd.md` becomes the document title unchanged (React escapes it; the storage key does not use it, not verified in MinIO).
- `GET /members?limit=abc` and `?role=GOD` are ignored (`200`) while `?status=BOGUS` is `400`.

## 3a. Fixes and re-check (uncommitted)

| # | Fix | Where |
|---|---|---|
| B1 | A type mismatch is `400 VALIDATION_FAILED` naming only the parameter, never the value. New unit test. | `common/GlobalExceptionHandler.java`, `GlobalExceptionHandlerTest.java` |
| U1 | At phone width the audit log is a list of cards; the table stays from 768 px up. | `app/(app)/audit/page.tsx` |
| U2 | The documents list shows the English text by `failureCode` (the same text the upload dialog uses). The Vietnamese sentence stays in core-api and ai-service because tests and the ai-service contract rely on it. | `app/(app)/documents/page.tsx` |
| U3 | "Try again" button on the Knowledge gaps list and the conversation list. The 25 s delay and the proxy status are not changed. | `components/app/ErrorNote.tsx`, `gaps/page.tsx`, `ConversationList.tsx` |
| F1 (TEST-REPORT-003) | Confirm dialog defaults are "Cancel" and "Confirm" (were "Hủy" and "Xác nhận"). | `components/ui/confirm-dialog/ConfirmDialog.tsx` |
| F2 (TEST-REPORT-003) | Category copy now says deleting moves its documents to uncategorized. | `NamedListPanel.tsx`, `CategoriesPanel.tsx` |

Checked after the fixes: core-api unit tests (131), `validate-build.ps1 -Scope web` (lint, build, 213 Vitest), E2E suite 40 passed, all 21 malformed-input probes now `400`, and in a browser the audit cards at 375 px, "Cancel" and the new category text. Not re-checked in a browser: the "Try again" button (needs ai-service stopped for about 25 s) and the English failed-document text (needs a failed ingestion). U4 is left as is (default visibility and ignored list filters may be intended).

## 4. What was not checked

- Chat, answers, citations, knowledge-gap creation (LLM).
- A real failed ingestion (corrupt or password-protected PDF), the quota limit (50 documents / 200 MB), invitation expiry by time, refresh-token replay in a real browser.
- The Documents page with ai-service down (the screenshot was taken while the page was still loading; inconclusive).
- Safari and Firefox; widths other than 375, 768 and the 800 px desktop pane.

## 5. Proposed scenarios

- Every list endpoint with a malformed filter returns `400` (covers B1).
- Audit log at 375 px shows Action and Details.
- With ai-service stopped, Chat and Knowledge gaps show an error and a retry.
- A corrupt PDF reaches `FAILED` and the document row shows an English reason.
