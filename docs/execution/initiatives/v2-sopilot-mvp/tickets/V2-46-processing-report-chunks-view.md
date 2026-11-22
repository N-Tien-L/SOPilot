---
id: V2-46
title: "ai-service + web: processing report (detected document type, chunking strategy, sample page with chunks outlined)"
type: feature
status: review # todo | in_progress | review | done | blocked
created: 2026-11-22
updated: 2026-11-22
author: "Owner"
scope: web
priority: P2
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-22, V2-32]
blocks: [V2-18, V2-47]
blocked_reason: ""
branch: "feat/web-processing-report"
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/components/ai-service.md
  - docs/architecture/diagrams/ingest-strategy-preview.excalidraw
---

# TICKET V2-46: Processing report

> **Scope:** `web` (with one read-only ai-service endpoint) | **Size:** `M` | **Priority:** `P2`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `feat/web-processing-report`

## 1. Context & goal
Pipeline steps extraction, cleaning and chunking are invisible in the UI. After a document is `READY`, a reader sees: the detected document family and the evidence, the chunking rules of that family, and a page of the canonical Markdown with each chunk outlined. Wireframe: [ingest-strategy-preview](../../../../architecture/diagrams/ingest-strategy-preview.excalidraw).

Owner decisions 2026-11-22: **D1** the sample page is a slice of the canonical Markdown (no PDF bitmap, no bounding boxes); **D2** a second tab on the document page next to the recognized content (FR-31); **D3** whoever may read the document may see the report (same rule as `/content`); **D4** recorded as an addition to FR-31 (read only, no score, no editor).

## 2. Acceptance criteria
- [ ] `GET /ai/v1/documents/{documentId}/versions/{versionId}/processing-report` (TECH-V2-ai-service §7.7): active `READY` version the caller may read, else one `404`; family, signals, strategy ids with the current chunk config, per-chunk `ordinal, chunkType, sectionPath, pageStart/End, charStart/charEnd, tokenCount`, stats; no `markdown`, no `pages`, no chunk text in the list.
- [ ] Chunk text for a clicked chunk is read from the database on demand (`?ordinal=`), because split rows and steps repeat the whole row's range and their text is not a slice of the Markdown.
- [ ] Tab "Processing report" on `/documents/[id]` with the three blocks of the wireframe, a page picker (pseudo-pages for Markdown files), legend and stats. Chunks sharing or overlapping a range are drawn as one outline labelled like `#12-#14`.
- [ ] Strategy sizes are labelled "current configuration" (not stored per version).
- [ ] Tests: ai-service unit (response builder, signals) and integration (another workspace, department outside scope, non-active version, `FAILED`/`PROCESSING` are all `404`); Vitest for the grouping and segmenting logic with Vietnamese diacritics and an astral character; one Playwright scenario in TEST-PLAN-001.
- [ ] No document text in logs. No new dependency. No migration.
- [ ] PRD FR-31 addition and TECH §7.7 written; `./scripts/docs/check-docs.ps1` passes.
- [ ] Browser check with one document per family (`LEGAL_ARTICLES`, `ISO_PROCEDURE`, `MARKDOWN`, `PROSE`) at 1280 and 390 px, as owner, a department reader and a non-reader.

## 3. Guide
- Data already stored: `rag.extracted_documents` (`doc_family`, `language`, `extracted_meta`, `structure`) and `rag.chunks` (`chunk_type`, `section_path`, offsets, `token_count`).
- Signals are not stored: recompute with `family_of(resolve_outline(structure.elements))` (same input as at ingest), exposing the evidence from `docproc/chunk/family.py` without changing detection. Show the stored family as the truth.
- Reuse `/content` for `markdown` and `pages`, and `lib/viewer/offsets.ts` (`codePointToUtf16`, `pageSegments`) for offsets; convert on one side only.
- The chunk query states `c.workspace_id = :wid` and `c.version_id = a.active_version_id` in the same `tenant_tx` as the extracted-documents query.
- Out of scope: live per-step progress while processing, editing or re-chunking, bounding boxes on a PDF bitmap.

## 4. Testing
```powershell
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/run-tests.ps1 -Scope ai-service -Type integration   # Docker
./scripts/validate-build.ps1 -Scope web
./scripts/run-e2e.ps1
./scripts/docs/check-docs.ps1
```

## 5. Changed files
| Area | Action |
|---|---|
| `services/ai-service/src/sopilot_ai/api/documents.py` (or a sibling module), `docproc/chunk/family.py` (evidence helper) and tests | MODIFY / CREATE |
| `frontend/web/lib/api`, `lib/viewer`, `components/viewer`, `app/(app)/documents/[id]/page.tsx` | MODIFY / CREATE |
| PRD FR-31, TECH-V2-ai-service §7.7, `docs/architecture/api/http-conventions.md`, `services/ai-service/README.md`, TEST-PLAN-001 | MODIFY |

## 6. Results
Implemented on the working tree (not committed), 2026-11-22.

**ai-service.** `api/processing_report.py` (new router in `create_app`) and `family_evidence` in `docproc/chunk/family.py` (same constants as `family_of`, detection unchanged). The list carries no chunk text; `?ordinal=N` returns `content` and `indexText`. No migration, no core-api change.

**Frontend.** Tab "Processing report" on `/documents/[id]` (`components/viewer/ProcessingReport.tsx`); grouping and paging logic in `lib/viewer/chunks.ts` (chunks that share or overlap a range are one outline, `#12-#14`), copy in `lib/viewer/report-labels.ts`; Markdown files are cut into parts of 6 outlines because they have no pages.

**Evidence.**
- ai-service: `ruff check src tests` clean; unit 703 passed, 1 skipped, 15 xfailed (9 new in `test_processing_report.py`); integration 158 passed (new: report matrix over 5 principals x 3 documents, unknown version or chunk, another workspace; all `404`, never `403`).
- web: `validate-build.ps1 -Scope web` passed (lint, build, 230 Vitest, 17 new in `lib/viewer/chunks.test.ts`).
- e2e: `run-e2e.ps1` 43 passed (3 new in `06-processing-report.spec.ts`, TEST-PLAN-001 R1).
- Browser (Chromium pane, owner of a throwaway workspace): a Markdown SOP with a step table was detected as `ISO_PROCEDURE` (evidence: 4 SOP section words, 1 step table), three short sections merged into one outlined chunk, three step rows as three outlines, a clicked chunk showed its embedded text; a text-layer PDF was detected as `PROSE` with one page; 390 px stacks the three blocks with no horizontal overflow.

**Found on the way.** The U4 fix (upload requires `visibility`) made `tests/e2e` global setup and one spec fail with `400`; both now send `visibility` explicitly.

**Not verified.** A `LEGAL_ARTICLES` and a multi-page PDF with a step table in the browser; a Markdown file long enough to have several parts; Safari and Firefox; the report as a non-reader in the browser (covered by the API tests); the "Previous"/"Next" wrap fix was rebuilt into the web image but not re-checked by eye.
