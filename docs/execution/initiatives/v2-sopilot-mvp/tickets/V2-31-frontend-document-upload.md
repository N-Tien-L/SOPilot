---
id: V2-31
title: "Frontend: multi-document upload and processing tracking"
type: feat
status: todo
created: 2026-10-24
updated: 2026-11-13
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
- [ ] Select at most 10 files per batch (selecting an 11th file is blocked with a message), send one upload request per file, at most 3 concurrently; each file shows the status "Uploading" ("Đang tải lên"), "Processing" ("Đang xử lý"), "Ready" ("Sẵn sàng") or an error with its own reason (PRD-V2 FR-30). After upload only "Processing" is shown, with no content link until `READY`.
- [ ] Independent results: a batch of 10 files with 2 failures (for example a scanned PDF and a `.txt`) still lets the other 8 proceed; failed files get their own action: "Retry" ("Thử lại") for transient errors, "Replace file"/"Delete" ("Thay file"/"Xóa") for content errors (the code table in TECH-V2-core-api §5.5), "Resend" ("Gửi lại") on network errors; retrying does not resend files that succeeded.
- [ ] Show the right message for `409 DUPLICATE_DOCUMENT` (with a link to the existing document), `409 DOCUMENT_UNCHANGED` ("The file content has not changed", "Nội dung file không thay đổi"), `409 VERSION_IN_PROGRESS`, `409 QUOTA_EXCEEDED` (with the quota and the amount used), `413`, `415`.
- [ ] Users are not made to wait: the dialog can be closed once no file is still uploading (the leave-page warning only while bytes are being sent); the document list refreshes its statuses while documents are processing and stops when none are.
- [ ] Upload accepts only PDFs with a text layer and MD; TXT is dropped from the MVP, DOCX deferred (FR-06). Show the API's `415` error with guidance (TXT → `.md`, DOCX → PDF with a text layer); no server-side conversion flow.

## 3. Guide
1. Declare types in `frontend/web/types` and the API client in `frontend/web/lib/api.ts` per TECH-V2-core-api/ai-service.
2. Implement in `frontend/web/app/` and `frontend/web/components/`, using the V2-15 shell.
3. Record browser evidence per acceptance criterion; update the frontend README.
- Update the related contracts in `.agent/context/` along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Browser: 10/11 files, the 3-upload limit, partial failure, per-file retry, 409/413/415, closing the dialog and polling stopping at the right time.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit. Build/lint does not replace UC-04/UC-12 evidence.
