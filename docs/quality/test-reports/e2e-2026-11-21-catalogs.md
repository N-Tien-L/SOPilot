---
id: TEST-REPORT-003
title: "E2E walkthrough: categories, departments and publishers, 2026-11-21"
status: draft
created: 2026-11-21
updated: 2026-11-21
author: "Owner"
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/quality/test-plans/test-plan-001-e2e-business-flows.md
---

# TEST-REPORT-003: E2E walkthrough, categories / departments / publishers

## 1. Verdict

No application bug that breaks a business rule. Two small UI wording problems and three points to confirm (section 3).

- Commit `6f8bf49` plus many uncommitted changes. Docker was off at the start; I started it, then ran `docker compose up -d --build core-api web ai-service` and started `ai-worker`. Flyway chains were applied by the infrastructure start.
- Docker Desktop would not start because of a broken socket file (`%LOCALAPPDATA%\docker-secrets-engine\engine.sock`). I renamed that folder to `docker-secrets-engine.broken` (outside the repo, with the owner's approval). No volume was touched.
- Browser pane was about 800 px wide for the desktop pass; the phone pass used 375 px.

## 2. What was run

| Run | Result |
|---|---|
| Suite 01 to 05 (`./scripts/run-e2e.ps1 -Keep`) | 40 passed, 0 failed |
| About 60 HTTP edge checks as owner, admin and member (script, not committed) | 0 app bugs |
| Browser: Categories tab, Departments screen, dialogs, phone width | 2 wording findings |

Proven by the HTTP checks:

| Area | Proven |
|---|---|
| Categories | Owner and admin create, rename, archive, delete; a member gets `403`. Duplicate name (any case) is `409 CATEGORY_NAME_TAKEN`; blank, 200 characters, bad status and empty patch are `400`. An archived category cannot be assigned (`400 CATEGORY_ARCHIVED`). Deleting a category in use succeeds and the document becomes uncategorized (as designed in core-api §3 and `ON DELETE SET NULL`). |
| Departments | Owner and admin create; a member gets `403`. Duplicate name `409`, blank or 200 characters `400`. Delete is refused while members, pending invitations or documents exist (`409 DEPARTMENT_IN_USE`, counts in `details`). Archive and restore work; unknown id is `404`. |
| Publishers | A department publisher must belong to the department (`409 PUBLISHER_NOT_IN_DEPARTMENT`); an unknown user is `409 MEMBER_NOT_ACTIVE`. Assigning twice is idempotent. The workspace publisher can be replaced and restored. Removing a publisher twice is `204`. |

## 3. Findings

### F1. Default Cancel label is Vietnamese (low, fixed afterwards: see TEST-REPORT-004 section 3a)

Every confirm dialog that does not pass its own label shows "Hủy" instead of "Cancel" (seen in Delete category and Delete department). Source: `frontend/web/components/ui/confirm-dialog/ConfirmDialog.tsx:52`, `cancelLabel = 'Hủy'`. UI copy is English (owner decision 2026-11-14).

### F2. Delete category text contradicts the behaviour (low, copy fixed afterwards)

The Categories tab says "delete works only while no document uses it", and the dialog says "This works only while nothing uses it; otherwise archive it instead." In fact the API deletes a category that documents use and moves them to "uncategorized" (core-api §3, by design). Steps: assign a category to a document, delete it in the UI or `DELETE /categories/{id}`, get `204`. Either change the copy or add a guard like `DEPARTMENT_IN_USE`; the design currently says delete is allowed.

### F3. Department delete error gives no counts (info)

The API returns `details: {members: 2, pendingInvitations: 1, documents: 2}`, but the dialog shows only "The department still has members, pending invitations or documents." Showing the numbers would tell the owner what to clear first.

### F4. To confirm with the owner (info)

- A plain member can `GET /publishers` and `GET /departments` (`200`); the Departments screen is hidden for members, but the API is open for reading. Plan M2 only says members cannot assign publishers.
- The workspace publisher can be set to a person who is also a department publisher (`PUT /publishers/workspace` with the Alpha publisher returned `204`).
- Validation answers differed in shape: category errors carried `details.fields`, department errors did not. Fixed afterwards: department name errors now return `details.fields.name` like categories (`DepartmentService.validName`); core-api unit tests pass (130), not rebuilt into the running image.
- Owner decision 2026-11-21: the first two points stay as they are.

## 4. What was not checked

- Chat and answers (no provider check).
- Safari, Firefox; any desktop width above the 800 px pane.
- Archive from the Departments UI and the archived view; focus returning to the button after a dialog closes.
- The admin and member views of Departments and Categories were covered by the suite, not walked by hand.

## 5. Proposed scenarios

- Delete a category that a document uses: document shows "uncategorized" and still opens.
- Archive a department that has documents: its documents stay readable by its members.
- A department publisher is removed from the department (member moved): publisher assignment is cleared or refused.
- Confirm dialogs: every cancel button reads "Cancel".

## 6. Cleanup

The kept workspace was deleted with `pnpm --dir tests/e2e cleanup` (passed).
