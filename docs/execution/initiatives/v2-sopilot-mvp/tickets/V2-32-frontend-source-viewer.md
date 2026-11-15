---
id: V2-32
title: "Frontend: recognized content and the citation viewer"
type: feat
status: in_progress
created: 2026-10-24
updated: 2026-11-15
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12, V2-15]
blocks: [V2-17]
branch: "feat/web-v2-32"
assignee: pair
---

# TICKET V2-32: Frontend: recognized content and citation viewer

> Translated from Vietnamese on 2026-11-13; content unchanged. UI strings are given in English with the original Vietnamese in quotes where the UI text is specified.

## 1. Context & goal
Scope split from V2-15 (XL) on 2026-10-24; the approved PRD/TECH requirements are unchanged. Use the frontend-delivery skill and `.claude/rules/frontend.md` when implementing. FR-14/FR-31, TECH-V2-ai-service §7.3/§7.5.

## 2. Acceptance criteria
- [ ] The "Content recognized by the system" screen ("Nội dung hệ thống nhận diện", FR-31): opens only when `currentVersion` exists (`READY`); a PDF shows the original file (signed URL) next to the canonical Markdown, and clicking a "Page N" ("Trang N") marker jumps the PDF to that page; narrow screens use two tabs; MD shows the canonical Markdown plus a download-original button. Version label: when `latestVersion` differs from `currentVersion`, show "Version N is used for Q&A; version N+1 is processing / failed" ("Phiên bản N đang dùng để hỏi đáp; phiên bản N+1 đang xử lý / xử lý lỗi"). Warnings appear only when the API returns `warnings`; removed boilerplate blocks are listed collapsed. A fixed sentence: `READY` means processing finished, not that the content has been checked. No editor and no "checked" button.
- [ ] Changed 2026-11-14 (owner decision, frontend NFRs): the original PDF is shown in the browser's native viewer opened at `#page=N` (signed URL), loaded on demand when the user asks for the source file or follows a "Page N" marker; no PDF library. Highlighting exists only on the canonical Markdown view.
- [ ] Safe Markdown rendering: no `rehype-raw` (unlike the old `DocumentViewerModal`); an MD fixture containing `<script>`, `<img onerror>` and an external image renders as text/links, runs no script and does not load the external image.
- [ ] Outside read access (FR-25) or for a document not yet `READY`: the viewer reveals no content (API `404`).
- [ ] Citation viewer: clicking `[n]` opens the right PDF page / passage and highlights the source by UTF-16 offset on the canonical Markdown (FR-14); shares the display component with the FR-31 screen.
- [ ] Citations of an old version show only the snapshot/label; the current viewer is not called when `isCurrentVersion=false`.
- [ ] Check on Chrome/Firefox: PDF page jumps, UTF-16 offsets with emoji, narrow screens, revoked access returning 404.
- [ ] Changed 2026-11-14: unit tests (Vitest from V2-38) for the UTF-16 offset to range mapping, including emoji.

## 3. Guide
1. Declare types in `frontend/web/types` and the endpoint calls on the V2-38 API client (`frontend/web/lib/`) per TECH-V2-core-api/ai-service.
2. Implement in `frontend/web/app/` and `frontend/web/components/`, using the V2-15 shell.
3. Record browser evidence per acceptance criterion; update the frontend README.
- Update the related contracts in `docs/architecture/` along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Browser: PDF/MD, multi-page pages/tables, emoji, XSS/external images, current/latest version, not yet READY and revoked access.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit. State which browsers were not checked.

## 5. Progress notes and evidence (2026-11-15, `in_progress`, not committed)

**Built:** `/documents/[id]` (FR-31 screen), `components/viewer/{ContentViewer,SafeMarkdown,CitationViewerModal}`, `lib/viewer/{offsets,labels}.ts`, `useDocument` / `useDocumentContent`, `getDocumentContent`, the "Open in document" action under an expanded source in chat, the document title link in the list, and the duplicate-upload link now pointing at `/documents/<id>`.

**Commands:** `./scripts/validate-build.ps1 -Scope web` → build, lint and 168 Vitest tests pass (offset mapping with emoji, labels, safe-Markdown fixture with `<script>` / `<img onerror>` / external image / `javascript:` link, `baseOffset` highlighting). `./scripts/docs/check-docs.ps1` → passed (13 pre-existing warnings).

**Browser (Playwright 1.65 driving Chromium and Firefox from the local Playwright cache; real compose core-api + ai-service + ai-worker, dev login, own test workspace):**
- MD document with emoji, Vietnamese, a table and a hostile fixture: text shown, no `<script>`/`<img>` in the pane, `document.title` unchanged, no request to the external image host, no dialog; wide and 390 px.
- Real question → citation `charStart 25, charEnd 1073` (code points; the Markdown is 1079 UTF-16 units): the source view marks exactly "Tài liệu này…" to "…trước khi nghỉ." (a naive slice would start one unit early and end six short). Escape closes the dialog.
- Citation of a replaced version (two newer versions uploaded): "Old version" label, stored passage, no "Open in document", zero `/content` calls.
- 21-page PDF: 21 "Page N" markers, no `download-url` call and no iframe until the first click, iframe at `#page=5` then `#page=9` with one signed URL reused, narrow screen switches to the PDF view; both browsers.
- 404: an unknown id and another user's workspace both show the single "not available" screen (API `404`, no content).

**Mock-checked only:** the "Version N is used for Q&A; version N+1 is processing / failed to process" label and the "no current version" state (the document response was rewritten in the browser; MD ingest finishes too quickly to catch live). A real `FAILED` version was not produced. Revoking access while a viewer is open was not exercised (department visibility is V2-33); the cross-workspace 404 stands in. Not checked: Safari, a real inline signed URL (below).

**core-api change (owner approved 2026-11-15):** `GET /documents/{id}/download-url?disposition=attachment|inline` (default `attachment`, other value `400 VALIDATION_FAILED`); `inline` signs `Content-Disposition: inline` (`StorageClient.presignGet(..., inline)`, `S3StorageClient`). Content type comes from the validated file type stored at upload. Tests: `DocumentServiceTest` (flag passed through), `S3StorageClientIT` (real MinIO returns `inline; filename*=...` and `application/pdf`), `DocumentLifecycleIT` (default, `attachment`, `inline`, `evil` → 400). `./mvnw verify` in `services/core-api`: 126 unit + 249 integration tests, BUILD SUCCESS. The compose `core-api` image was rebuilt (`up -d --build --no-deps core-api`) and checked live: no param, `inline` and `attachment` → 200, `evil` → 400, and the signed URL fetched from MinIO answers `Content-Disposition: inline` with `application/pdf`. The frontend viewer asks for `inline`; the "Download original" button keeps the default. Docs: TECH-V2-core-api §5.5, `services/core-api/README.md`, `http-conventions.md`. `./scripts/run-tests.ps1 -Scope core-api` aborts on a Mockito stderr warning in this PowerShell setup (pre-existing); Maven was run directly.

**Harness shim (still needed):** in compose, core-api signs URLs for `http://minio:9000`, which a host browser cannot resolve. The browser runs route that host to the published MinIO port; no header is rewritten any more. Running core-api from source with a browser-reachable `SOPILOT_S3_ENDPOINT` avoids the shim; a public presign endpoint is not implemented.

**Videos (not committed; `docs/quality/evidence/` is gitignored), `docs/quality/evidence/v2-32/`, Chromium (headed) and Firefox (headless), each with on-screen captions:** `v2-32-s1-recognized-content-markdown-*`, `s2-pdf-native-viewer-page-jump-*` (real inline URL, pages 5, 9, 14), `s3-citation-viewer-highlight-*` (real question, highlight, exact range), `s4-old-version-citation-*`, `s5-narrow-screen-tabs-*` (390 px), `s6-no-access-404-*`. The version label and the "no current version" state are not in the videos (mock-checked only).

**Other notes:** citation offsets are code points (only `pages` carry `charStart16`), converted in the browser. AC "clicking `[n]` opens the viewer" is two steps today (expand, then "Open in document"). Review (Opus 5.5): 1 blocker (the one above), 4 warnings fixed (content cache `staleTime: 0`, highlight memo, overlapping signed-URL asks, ARIA tabs replaced by pressed toggles), notes on duplicate keys fixed.
