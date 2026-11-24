---
id: V2-31
title: "Frontend: multi-document upload and processing tracking"
type: feat
status: done
created: 2026-10-24
updated: 2026-11-16
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-12, V2-15, V2-36]
blocks: [V2-17]
branch: "feat/web-v2-31"
assignee: pair
---

# TICKET V2-31: Frontend: multi-document upload and processing status

> Translated from Vietnamese on 2026-11-13; content unchanged. UI strings are given in English with the original Vietnamese in quotes where the UI text is specified.

## 1. Context & goal
Scope split from V2-15 (XL) on 2026-10-24; the approved PRD/TECH requirements are unchanged. Use the frontend-delivery skill and `.claude/rules/frontend.md` when implementing.

## 2. Acceptance criteria
- [x] Select at most 10 files per batch (selecting an 11th file is blocked with a message), send one upload request per file, at most 3 concurrently; each file shows the status "Uploading" ("Đang tải lên"), "Processing" ("Đang xử lý"), "Ready" ("Sẵn sàng") or an error with its own reason (PRD-V2 FR-30). After upload only "Processing" is shown, with no content link until `READY`.
- [x] Independent results: a batch of 10 files with 2 failures (for example a scanned PDF and a `.txt`) still lets the other 8 proceed; failed files get their own action: "Retry" ("Thử lại") for transient errors, "Replace file"/"Delete" ("Thay file"/"Xóa") for content errors (the code table in TECH-V2-core-api §5.5), "Resend" ("Gửi lại") on network errors; retrying does not resend files that succeeded.
- [x] Show the right message for `409 DUPLICATE_DOCUMENT` (with a link to the existing document), `409 DOCUMENT_UNCHANGED` ("The file content has not changed", "Nội dung file không thay đổi"), `409 VERSION_IN_PROGRESS`, `409 QUOTA_EXCEEDED` (with the quota and the amount used), `413`, `415`.
- [x] Users are not made to wait: the dialog can be closed once no file is still uploading (the leave-page warning only while bytes are being sent); the document list refreshes its statuses while documents are processing and stops when none are.
- [x] Upload accepts only PDFs with a text layer and MD; TXT is dropped from the MVP, DOCX deferred (FR-06). Show the API's `415` error with guidance (TXT → `.md`, DOCX → PDF with a text layer); no server-side conversion flow.
- [x] Changed 2026-11-14: unit tests (Vitest from V2-38) for the upload queue state machine: the 3-concurrent cap, per-file retry and independent failure.

## 3. Guide
1. Declare types in `frontend/web/types` and the endpoint calls on the V2-38 API client (`frontend/web/lib/`) per TECH-V2-core-api/ai-service.
2. Implement in `frontend/web/app/` and `frontend/web/components/`, using the V2-15 shell.
3. Record browser evidence per acceptance criterion; update the frontend README.
- Update the related contracts in `docs/architecture/` along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Browser: 10/11 files, the 3-upload limit, partial failure, per-file retry, 409/413/415, closing the dialog and polling stopping at the right time.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit. Build/lint does not replace UC-04/UC-12 evidence.

## 5. Progress notes and evidence (2026-11-15, `review`)

**Owner acceptance 2026-11-16:** the owner accepted the ticket; status `review` → `done`. The evidence below is unchanged.

Branch `feat/web-v2-31`, from `develop` (V2-15 had merged, PR #17). Not committed.

**Built:** pure queue state machine `lib/upload/queue.ts` (10 files per batch, 3 in flight, independent per-file state, retry that touches only the failed file), `failure.ts` (API error and FAILED code → English message and action), `validate.ts` (client type and 20 MB check), `controller.ts` (requests and polling, outside React), `store/upload-store.ts`, `UploadDialog` and `UploadManager` mounted in the `(app)` layout, the Upload button on `/documents`, upload/retry/delete calls in `lib/api/endpoints.ts`. A workspace switch aborts the batch (R7).

**Decisions and deviations**
- Uploads are `WORKSPACE`-visible with no category or tags; department visibility and metadata are V2-33. The Upload button shows only for the workspace publisher (`GET /members/me` → `publisherOf.workspace`); an OWNER who is not the publisher may delete and transfer but never write content (`DocumentWritePolicy`), so is not offered it (`403 NOT_PUBLISHER` is shown per file). A department publisher cannot upload through this UI until V2-33.
- The leave-page warning is on while a file is uploading **or waiting to be sent** (waiting files would be lost on leaving).
- A file whose bytes are sent (processing, ready) no longer occupies one of the 10 batch slots, so a second batch can start while the first is processing.
- Failure text is local English by `failureCode`: core-api stores a Vietnamese sentence in `failureMessage`, which the English UI does not show (the documents list still shows it for FAILED rows; not changed here).
- `DUPLICATE_DOCUMENT` names the existing document and links to `/documents?q=<title>` (the list gained a title search); a link straight to the document waits for the V2-32 viewer.
- Doc fix: TECH-V2-core-api §5.0 said `422 QUOTA_EXCEEDED`; corrected to `409` (code, §3.3 and this ticket), with the note in `http-conventions.md`.
- Shared `Modal` gained keyboard focus handling (focus on open, Tab trap that also catches focus lost to `<body>`, restore to the opener). Behaviour only, no CSS.
- Leaving with unfinished uploads (workspace switch, sign-out) asks for confirmation (`lib/upload/guard.ts`); polling is a `setTimeout` chain that gives up after 5 failed reads and offers Retry.

**Verification**
- `./scripts/validate-build.ps1 -Scope web`: build, lint and Vitest pass (138 tests in 10 files; upload tests in `lib/upload/{queue,failure,controller}.test.ts`: 3-concurrent cap, 10/11 files, independent failure, per-file retry, replace, polling stop and give-up, workspace reset, leave prompt).
- Real stack (compose Postgres, MinIO, core-api, ai-service and ai-worker; `pnpm dev`; `playwright-core` already installed globally by another tool, run from the session scratchpad, nothing added to the repo): Chromium 159 and Firefox 159, 53 of 53 checks each after the second round. Covers 10 and 11 files, 3 requests in flight, closing the dialog mid-upload, `beforeunload` only while sending, partial failure (txt, oversize, real `409 DUPLICATE_DOCUMENT`, network error → Resend, only the failed file resent), Replace file, real `415` (not a PDF, invalid UTF-8), documents reaching READY with the real worker, polling stopping, 375 px width with no horizontal overflow, keyboard focus (in on open, Tab trap, back to the opener), the sign-out prompt with Cancel keeping uploads, the duplicate link filtering the list, poll give-up.
- Mock-only (`page.route`): `413`, `QUOTA_EXCEEDED`, `DOCUMENT_UNCHANGED`, `VERSION_IN_PROGRESS` responses, the FAILED status of documents after upload (the retry, version-upload and delete requests were real), `GET /members/me` roles for the Upload gate, and 503 status reads for poll give-up. A real corrupt PDF cannot be used: see the finding below.
- Screenshots (local, git-ignored): `docs/quality/evidence/v2-31/`.

**Review (fresh Opus 5.5 `v2-reviewer`, one round, no blocker).** Fixed: Delete and Retry stayed available only while the last failure was a processing failure (a rejected replacement removed them); a processing batch blocked new uploads; a document deleted elsewhere vanished from the list silently (now shown as failed); polling re-rendered on every round; the wrong verb for a 403 on retry or delete; one early-return path did not refill upload slots; a misnamed test. **Second round (owner asked to resolve the open items):** dialog focus, the switch/sign-out prompt, poll give-up and non-overlapping rounds, the publisher gate on the Upload button, the duplicate link target, a `controller.test.ts` (18 tests) and the `422` doc fix are done. A second fresh Opus 5.5 review of that delta found no blocker (3 warnings, 8 notes). Fixed: the OWNER gate (the server lets only the workspace publisher create), the prompt before creating a workspace and before leave/delete in settings, "retry" after an unreadable status no longer reprocesses, the reopen button stays mounted so focus returns to it. **Known gaps, not fixed:** a workspace switch or sign-out made in *another tab* cancels this tab's uploads without a notice (broadcast session change); the Delete confirm does not take focus; the title search is not written to the URL (no debounce); the `Modal` suits siblings, not nested modals or an `autoFocus` child; `controller.test.ts` reset tests would not catch a removed abort guard, and the `setTimeout` chain is checked in the browser only.

**Found outside this ticket (core-api / ai-service):** a corrupt PDF stays `PROCESSING` in core-api although the worker marked it failed: the worker's `FAILED` callback is accepted, but the separate `PROCESSING` event of the same version can be delivered after it and moved the version back to `PROCESSING` (or got `409 INVALID_TRANSITION` after `READY` and went dead). Reproduced twice with a 15-byte `%PDF-` file; the document never left processing, so the UI kept showing "Processing". Tracked and fixed in [V2-41](V2-41-core-api-version-status-callback-order.md).

**Not verified:** a real FAILED document through the whole stack (blocked by the finding above), a real `413` and `409 QUOTA_EXCEEDED`, a department publisher uploading, a real workspace switch during an upload (the prompt was checked on sign-out only), full keyboard-only use, Safari and Edge, a person using it by hand.
