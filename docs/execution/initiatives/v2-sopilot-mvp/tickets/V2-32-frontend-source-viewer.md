---
id: V2-32
title: "Frontend: recognized content and the citation viewer"
type: feat
status: todo
created: 2026-10-24
updated: 2026-11-13
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
- [ ] Safe Markdown rendering: no `rehype-raw` (unlike the old `DocumentViewerModal`); an MD fixture containing `<script>`, `<img onerror>` and an external image renders as text/links, runs no script and does not load the external image.
- [ ] Outside read access (FR-25) or for a document not yet `READY`: the viewer reveals no content (API `404`).
- [ ] Citation viewer: clicking `[n]` opens the right PDF page / passage and highlights the source by UTF-16 offset on the canonical Markdown (FR-14); shares the display component with the FR-31 screen.
- [ ] Citations of an old version show only the snapshot/label; the current viewer is not called when `isCurrentVersion=false`.
- [ ] Check on Chrome/Firefox: PDF page jumps, UTF-16 offsets with emoji, narrow screens, revoked access returning 404.

## 3. Guide
1. Declare types in `frontend/web/types` and the API client in `frontend/web/lib/api.ts` per TECH-V2-core-api/ai-service.
2. Implement in `frontend/web/app/` and `frontend/web/components/`, using the V2-15 shell.
3. Record browser evidence per acceptance criterion; update the frontend README.
- Update the related contracts in `.agent/context/` along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Browser: PDF/MD, multi-page pages/tables, emoji, XSS/external images, current/latest version, not yet READY and revoked access.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit. State which browsers were not checked.
