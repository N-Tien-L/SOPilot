---
id: V2-47
title: "ai-service: chunk quality fixes found on the pilot corpus (false headings, letterhead tables, split step rows, table of contents, tiny legal fragments)"
type: fix
status: in_progress # todo | in_progress | review | done | blocked
created: 2026-11-22
updated: 2026-11-22
author: "Owner"
scope: ai-qa
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20, V2-21, V2-22, V2-46]
blocks: [V2-18]
blocked_reason: ""
branch: "fix/ai-chunk-quality"
refs:
  - docs/quality/test-reports/e2e-2026-11-22-ingest-detection-chunking.md
  - docs/architecture/components/ai-service.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-22-structure-aware-chunking.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-21-boilerplate-and-metadata.md
---

# TICKET V2-47: Chunk quality fixes

> **Scope:** `ai-qa` | **Size:** `L` (two phases, see section 3) | **Priority:** `P1`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `fix/ai-chunk-quality`

## 1. Context & goal
[TEST-REPORT-005](../../../../quality/test-reports/e2e-2026-11-22-ingest-detection-chunking.md) ran the real pipeline over the pilot corpus and the processing report (V2-46) made the chunks visible. The outline is drawn correctly; the defects are in the cleaning and chunking code. For each one the raw Docling output (`extract()`) was compared with the PDF text layer to find who is at fault (evidence in the report's addendum).

| # | Symptom | Raw Docling output | Where the fault is |
|---|---|---|---|
| 1 | `vn-vbhn109`: two body lines ("1 Nghị định số 366/…/NĐ-CP có căn cứ ban hành như sau:", "2. Nghị định này bãi bỏ toàn bộ các Nghị định:") become section titles, so their text leaves the chunk content | `paragraph` (correct) | `docproc/chunk/headings.py:23` `_DOTTED` (the dot after the number is optional) and `_classify` (no rejection of a trailing ":"; `_is_lone_numbered_title` at `:140` has it) |
| 2 | `tb-qt05`: the page letterhead "CẢNG VỤ THÁI \| QUY TRÌNH… \| Mã hiệu: \| QT.05" is chunked as `SECTION` (2 chunks) and as fake `PROCEDURE_STEP` ("Cột 1: CẢNG VỤ THÁI") | a 3x4 `table` on pages 5, 7, 8, 9 with the text split differently per page ("HÀNG HẢI Ngày ban hành:", empty cells) | `docproc/clean/boilerplate.py` `mark_repeated_header_footer` (`:101`, threshold `max(header_footer_min_pages, header_footer_ratio x page_count)` at `:130`) and `mark_frame_blocks` do not mark it. Not marked means it stays `role=content` and also blocks the page-to-page table join |
| 3 | `tb-qt05`: a step row cut at a page break is not stitched; steps 5 and 6 are labelled `Cột 1/2/3` instead of `TT/Hoạt động/…`; step 1 ends in "+ Tình hình thực hiện \| \|" | one table per page, `header_rows=0`, first row with empty leading cells that carries the overflow text of the previous row | `docproc/tables.py` `join_continued_tables` already passes over frame elements and accepts `header_rows==0` (`:47`, `:63`; test `tests/unit/test_clean_corpus_fixes.py:147`). So the join misses because of cause 2 (the letterhead is still content between the tables) and because the overflow row is kept as a row of its own. Why `Cột N` appears is **not proven**: `procedure_table.py:62` uses it only when a header cell is empty |
| 4 | `tb-qt05` chunk #1 (228 to 285 tokens) is the table of contents followed by the distribution list | `list_item` "1. MỤC ĐÍCH"… (correct) | `docproc/chunk/chunker.py` indexes a section that is only a list of section titles |
| 5 | `vn-vbhn109`, `vn-qd1308`, `vn-qd82`: chunks of 9 to 55 tokens ("Số:", "/2026/VBHN-NĐ-NHNN", a line of underscores) | decorative lines are in the PDF text layer; the "Số:" split is Docling's reading order | `chunker.py:102` never merges small sections for `LEGAL_ARTICLES`; `clean` keeps decorative lines |

Docling's own faults (reading order at the top of a page, inconsistent heading versus paragraph versus list item for the same kind of line) are not fixed here; this ticket only stops them from producing bad chunks.

Goal: no chunk of the pilot corpus is made of page furniture, a false heading, a table of contents or a decorative line, and a step table that continues on the next page gives whole steps.

## 2. Owner decisions needed before Phase B
- **Order with V2-45 and the eval harness.** `eval/sopilot_eval/docproc_chunks.py:66-67` raises when `clean_document` then `render` no longer reproduces byte for byte the frozen Markdown of `sop-main` (sha256 per document). Phase B changes that Markdown, so docproc-mode RQ runs and the `sop-main-v3` freeze of V2-45 stop working at HEAD. The owner decides: freeze `sop-main-v3` first and re-freeze after Phase B, or pin the docproc commit used by the eval. The implementer stops before Phase B until this is recorded here.
- **Reindex of the owner's local data** after merge (not done by this ticket).

## 3. Acceptance criteria
Work in two phases, one commit each, and run the checks between them. Failing tests first for every item (unit tests on synthetic `DocElement`s that mirror the raw output above; no Docker, no model download). Every rule has a negative test (a real procedure table, a short article, a numbered heading that ends in ":" in an ISO document).

**Phase A: heading and chunker rules (the stored Markdown does not change).**
- [ ] **1. False headings.** In `_classify`, a depth-1 numbered line needs `.` or `)` after the number, and a numbered line ending in `:` is not promoted (numbered branch only; `Điều n:`, `Chương n:` unaffected). The two quoted `vn-vbhn109` lines are no longer headings; `1. MỤC ĐÍCH`, `5.1`, `I.`, `Điều n` still are (V2-22 cases stay green).
- [ ] **4. Table of contents.** A section whose heading is a contents heading (`MỤC LỤC`, `Contents`, `Table of contents`) and whose body is only a list of items produces no chunk and its text is not in the chunk list; it stays in the Markdown and in the recognized-content view. The distribution list that follows is a separate section and is chunked as before. Negative test: a procedure whose steps are a numbered list under a normal heading is chunked.
- [ ] **5a. Tiny fragments in `LEGAL_ARTICLES`.** Small sections are merged into the next section before the first article heading (or, for a document whose articles are body lines, before the first body line that opens with `Điều n`); article sections are never merged with each other. A `TEXT` chunk with no letters is dropped (table chunks are not touched, numeric tables stay). `test_chunk.py:198` stays green.
- [ ] **6. Processing report copy.** `STRATEGY_RULES` for `LEGAL_ARTICLES` states "one chunk per article" (new rule id `ARTICLE_UNIT`, label in `lib/viewer/report-labels.ts`, a line in TECH §7.7, tests on both sides) and `OTHER_FAMILY_NOTES` is true after 5a ("short ones are never merged" is rewritten).
- [ ] Phase A gate: ai-service unit and integration suites, ruff, web gates, `cd eval; uv run pytest -q`, the corpus table (item 7) for Phase A. The stored Markdown is unchanged, so `NORMALIZER_VERSION` is not bumped, but chunks change: `python -m sopilot_ai.admin reindex --all --dry-run` is recorded (`admin.py:6`; a chunker-only change is not seen by the stale check).

**Phase B: cleaning and tables (the stored Markdown changes; needs the owner decision of section 2).**
- [ ] **2. Letterhead tables.** Find the failing condition first and record it in the ticket (which of the ratio `max(3, 0.4 x pages)`, `_EDGE_WINDOW`, `_MAX_FRAME_LABEL`, the rows-hit rule or the per-page text difference stops `tb-qt05` pages 5, 7, 8, 9). Change that condition only; do not lower the owner's 0.4 ratio of V2-21 globally. A table that repeats on the pages the rule requires, with the same shape and the same text after `fold` and with empty cells ignored (reuse the existing frame-table share, `_FRAME_TABLE_SHARE`, if it fits), is `boilerplate`, listed in `removedBlocks` and absent from the Markdown. A real step table is never removed (test: 3 or more pages of a 5-column step table with a repeated header row). Re-measure the V2-21 limits on the V2-19 corpus: leakage at most 10 percent, wrongful removal at most 2 percent.
- [ ] **3. Split step rows.** With the letterhead out of the way, the page-to-page join of `tb-qt05` pages 4 to 9 happens (existing join code; assert it). New: a continuation row with empty leading cells is stitched into the last row of the previous table (non-empty cell text appended to the same column of that row). Define and test: which page range the stitched row keeps (`chunker.py:392` gives a step one page), how `cell_spans` and `row_spans` shift, and a negative test for a next-page row that has an empty first cell but is a real new step (the guard of `tests/unit/test_clean_corpus_fixes.py:185`). Then find why steps 5 and 6 show `Cột N` and fix that cause; the expected result is 6 whole steps, each chunk labelled with the real column names.
- [ ] **5b. Decorative lines.** A paragraph that is only `_ - = * ~ .` and spaces is `boilerplate` (listed in `removedBlocks`).
- [ ] **8. Re-indexing.** `NORMALIZER_VERSION` (`docproc/render.py:13`) is bumped, the stale check reports the old versions (`admin.stale_count`, `/health`, the `index_out_of_date` log), and `reindex --dry-run` is recorded. Record the consequences in the ticket: (a) `rag.message_citations` stores character offsets with a `version_id`; a reindex rewrites the Markdown of the same version, so highlights of old conversations can drift; (b) `/health` reports degraded until the owner reindexes; (c) retrieval does not skip stale-normalizer chunks (`retrieval/search.py:39` filters only on model and revision) although the comment at `api/app.py:45-46` says it does: report this mismatch, do not fix it here. Reindexing the owner's data is not done by this ticket.
- [ ] Phase B gate: as Phase A, plus the corpus table and the eval harness check of section 2.

**Both phases.**
- [ ] **7. Corpus evidence.** Run the pilot corpus **before any code change** (baseline) and after each phase. The script of TEST-REPORT-005 lives only in a session scratchpad and `eval/check_chunks_corpus.py` reads V2-19 structured JSON (`--structured`) and does not report these counts: extend `eval/check_chunks_corpus.py` with a mode that runs `extract` on the pilot PDFs, or commit a new script next to it (stdlib plus `sopilot_ai.docproc`, offline models). It reports per file: family, chunk count, chunks under 64 tokens, chunks with no letters, uncovered body lines, step chunks. Hard conditions: the 4 scans still fail with `NO_TEXT_LAYER`; families do not change (`vn-qd1308`, `vn-qd82` stay `LEGAL_ARTICLES`); every V2-22 invariant (offsets, substring, procedure_row, token_budget) has 0 violations.
- [ ] **9. Eval comparability.** The RQ numbers of V2-07 and the sets of V2-37 and V2-45 were measured with the old chunker and Markdown. Say so in the handover notes (V2-18) and in TEST-REPORT-005; do not edit committed eval results. `cd eval; uv run pytest -q` stays green but uses synthetic data, so it does not prove the docproc path: the section 2 decision does.
- [ ] **10. Docs.** TECH-V2-ai-service §5 (heading rules, cleaning, chunking, families; no renumbering) states what changed; the addendum of TEST-REPORT-005 gets the result for findings F2, F4 and F5. F3 (a split step loses its number in the continuation chunk) is **not** fixed here and stays open.
- [ ] `./scripts/pre-commit-check.ps1` and `./scripts/docs/check-docs.ps1` pass, and `cd eval; uv run pytest -q tests/test_review_regressions.py -k plan`.

## 4. Guide
- Branch from `develop` only after V2-46 and the F1 detection fix (`headings.is_article_line`, `family.py`) are committed there; item 6 edits V2-46 files (`api/processing_report.py`, `lib/viewer/report-labels.ts`).
- Code: `docproc/chunk/headings.py`, `docproc/chunk/chunker.py` (`_merge_small`, `_sections`, the `LEGAL_ARTICLES` branch at line 102), `docproc/chunk/procedure_table.py`, `docproc/clean/boilerplate.py`, `docproc/tables.py`, `docproc/render.py`. Read V2-22 "Joining multi-page tables and remeasuring 2026-11-04" first. `docproc/extract/pdf.py` (`_merge_tables`) is read-only here (V2-22 kept the extractor unchanged).
- Raw Docling output of the cases is reproduced offline with `extract(pdf_bytes, name)` from `sopilot_ai.docproc` (`uv run --extra pdf`, models cached). The pilot corpus is local and gitignored (`datasets/extraction/pilot/local/corpus`); unit tests use synthetic elements so CI does not need it; a corpus test may exist only as `pdf`-marked and skipped when the files are absent.
- Smallest change per item; no change to Docling options or the extractor's element classification.
- Not in scope: Docling reading order and classification, OCR, merging articles, retrieval or ranking changes, F3, reindexing the owner's data, re-running RQ1 to RQ5.

## 5. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | Items 1 to 6 and Phase B items with synthetic elements, negative cases | `./scripts/run-tests.ps1 -Scope ai-service -Type unit` |
| Lint | | `./scripts/validate-build.ps1 -Scope ai` |
| Integration | The ingest path with the changed code (Docker) | `./scripts/run-tests.ps1 -Scope ai-service -Type integration` |
| Corpus | Baseline, after Phase A, after Phase B; invariants | the script of item 7 |
| Web | Item 6 labels | `./scripts/validate-build.ps1 -Scope web` |
| Eval | Harness imports and passes; docproc-mode decision of section 2 | `cd eval; uv run pytest -q` |
| Docs and plan | | `./scripts/docs/check-docs.ps1`; `cd eval; uv run pytest -q tests/test_review_regressions.py -k plan`; `./scripts/pre-commit-check.ps1` |

## 6. Changed files
| Area | Action |
|---|---|
| `services/ai-service/src/sopilot_ai/docproc/{chunk,clean}/`, `tables.py`, `render.py` and tests | MODIFY |
| `services/ai-service/src/sopilot_ai/api/processing_report.py`, `frontend/web/lib/viewer/report-labels.ts` (+ tests) | MODIFY (item 6) |
| `eval/check_chunks_corpus.py` (or a new script beside it) | MODIFY / CREATE (item 7) |
| TECH-V2-ai-service §5 and §7.7, TEST-REPORT-005 | MODIFY |

## 7. Results

### Corpus script (item 7)
`eval/check_chunks_pilot.py` (helpers and definitions in `eval/sopilot_eval/pilot_chunks.py`, tests in `eval/tests/test_pilot_chunks.py`) runs the ingest steps of `process_document` offline: `extract`, `clean_document` with `CleanConfig.from_env()` and the chunk `max_tokens`, `render`, `detect_family`, `chunk_document` with the `models.yaml` chunk config and the embedding tokenizer, title = file stem. The raw `extract()` output is cached per file hash (`eval/results/pilot-chunks/cache`, gitignored), so Docling runs once and later runs differ only by cleaning and chunking. Run from `services/ai-service`:

```powershell
$env:PYTHONPATH="src"; $env:HF_HUB_OFFLINE="1"; uv run --extra pdf python ../../eval/check_chunks_pilot.py --corpus ../../datasets/extraction/pilot/local/corpus --cache ../../eval/results/pilot-chunks/cache --out ../../eval/results/pilot-chunks/<label>.json
```

Columns: `<64` = chunks under `min_tokens` that are not `PROCEDURE_STEP`; `no letters` = chunks whose content has no letter (any kind); `uncovered` = body elements (outline level `None`) whose range overlaps no chunk (headings are excluded, their text is in `section_path`); `steps` = `PROCEDURE_STEP` chunks; `md sha` = first 8 hex of the sha256 of the rendered Markdown (equal before and after Phase A shows the stored Markdown did not change). Violations are all `chunk_invariants.INVARIANTS`.

### Baseline (2026-11-22, `f2995f3`, before any V2-47 code change)

| file | family | chunks | <64 | no letters | uncovered | steps | md sha | violations or failure |
|---|---|---|---|---|---|---|---|---|
| epa-qc | ISO_PROCEDURE | 54 | 1 | 0 | 0 | 0 | b71f13cc | 0 |
| epa-soil | ISO_PROCEDURE | 75 | 1 | 0 | 0 | 0 | 8a8601b9 | 0 |
| epa-sw | ISO_PROCEDURE | 42 | 0 | 0 | 0 | 0 | 8fa5f4c2 | 0 |
| fda-qms-sop | ISO_PROCEDURE | 22 | 1 | 0 | 0 | 0 | 768c5464 | 0 |
| k8s-disruptions | MARKDOWN | 16 | 2 | 0 | 0 | 0 | ce8cc1ee | 0 |
| k8s-drain | MARKDOWN | 9 | 3 | 0 | 0 | 0 | 13182cbb | 0 |
| nb-qt01 | ISO_PROCEDURE | 42 | 4 | 1 | 0 | 14 | 6bfa7650 | 0 |
| nb-qt02 | ISO_PROCEDURE | 20 | 3 | 0 | 1 | 7 | 916dc5f6 | 0 |
| nb-qt03 | ISO_PROCEDURE | 24 | 1 | 0 | 0 | 12 | dee5c74b | 0 |
| nb-qt04 | ISO_PROCEDURE | 13 | 1 | 0 | 0 | 6 | 44aa6282 | 0 |
| nb-thanhtra06 | ISO_PROCEDURE | 33 | 2 | 0 | 0 | 2 | 36a4efeb | 0 |
| nci-bdp-deviations | ISO_PROCEDURE | 38 | 6 | 0 | 0 | 0 | a0002f30 | 0 |
| nci-bdp-labeling | ISO_PROCEDURE | 12 | 0 | 0 | 0 | 0 | d55cc7a9 | 0 |
| nd30 | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| tb-qt01 | ISO_PROCEDURE | 22 | 1 | 0 | 0 | 2 | 325ba3a2 | 0 |
| tb-qt03 | ISO_PROCEDURE | 32 | 5 | 0 | 0 | 5 | dc781cc9 | 0 |
| tb-qt05 | ISO_PROCEDURE | 20 | 1 | 0 | 0 | 6 | eebd5f78 | 0 |
| vn-cv10065 | PROSE | 2 | 0 | 0 | 0 | 0 | 51da260f | 0 |
| vn-nq311-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-nq424-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-nq432-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-qd1308 | LEGAL_ARTICLES | 44 | 3 | 1 | 0 | 0 | 0875c136 | 0 |
| vn-qd82 | LEGAL_ARTICLES | 5 | 2 | 1 | 0 | 0 | df5d0071 | 0 |
| vn-tb425 | MARKDOWN | 5 | 0 | 0 | 0 | 0 | 55733f77 | 0 |
| vn-vbhn109 | LEGAL_ARTICLES | 37 | 3 | 0 | 0 | 0 | 7e6cb72a | 0 |

Invariants: offsets=0, substring=0, procedure_row=0, page_order=0, page_source=0, multi_page_table=0, token_budget=0.

Raw outline at the defect sites (from the cache): `vn-vbhn109` has three false numbered headings, all `paragraph`: "1 Nghị định số 366/2025/NĐ-CP có căn cứ ban hành như sau:", "2. Nghị định này bãi bỏ toàn bộ các Nghị định:", "3. Nghị định này bãi bỏ một phần các Nghị định:" (the ticket named two). In `tb-qt05` the table of contents is a `heading` "MỤC LỤC", a `paragraph` line, then seven `list_item`s ("1." "MỤC ĐÍCH" …) that the outline promotes to level-1 headings with no body; `_merge_small` then folds them with the heading-level "DANH SÁCH PHÂN PHỐI TÀI LIỆU:" section into chunk #0 (285 tokens).

### Phase A (2026-11-22, working tree on `fix/ai-chunk-quality`, after review round 1 fixes)

Code: `docproc/chunk/headings.py` (item 1), `docproc/chunk/chunker.py` (items 4 and 5a), `api/processing_report.py` and `lib/viewer/report-labels.ts` (item 6); tests `tests/unit/test_headings_v2_47.py`, `tests/unit/test_chunker_v2_47.py`, `test_processing_report.py`, `lib/viewer/report-labels.test.ts`; TECH-V2-ai-service §5.4 and §7.7.

Decisions taken while implementing (orchestrator, within the ticket's wording):
- The no-letter `TEXT` drop applies to `LEGAL_ARTICLES` only (item 5a scope); a letterless `TEXT` chunk that overlaps a table element is kept, because a small table is packed as `TEXT` and "numeric tables stay". Decorative lines in other families are item 5b (Phase B).
- The `":"` rule rejects only numbered paragraphs; numbered list items and converter headings that end in `":"` keep their numbered level (`5.1 Kiểm soát tài liệu:`, `5.1. Lưu đồ:`), as before V2-47.
- A table of contents heading must be exactly `Mục lục` / `Contents` / `Table of contents` (accents, case, trailing `:` ignored, no numbering): `6. Contents` with a kit list is a real section. A section before a dropped table of contents is never merged across it, so every kept `TEXT` chunk stays one Markdown slice.
- Item 6 copy says "one chunk per article **heading**": a decision whose articles are body lines (`vn-qd1308`, `vn-qd82`) keeps them in one section and packs them like text. Cutting sections at article lines is out of scope here (it changes the outline, which the ticket keeps).

| file | family | chunks | <64 | no letters | uncovered | steps | md sha | violations or failure |
|---|---|---|---|---|---|---|---|---|
| epa-qc | ISO_PROCEDURE | 54 | 2 | 0 | 3 | 0 | b71f13cc | 0 |
| epa-soil | ISO_PROCEDURE | 75 | 1 | 0 | 0 | 0 | 8a8601b9 | 0 |
| epa-sw | ISO_PROCEDURE | 42 | 0 | 0 | 0 | 0 | 8fa5f4c2 | 0 |
| fda-qms-sop | ISO_PROCEDURE | 22 | 1 | 0 | 0 | 0 | 768c5464 | 0 |
| k8s-disruptions | MARKDOWN | 16 | 2 | 0 | 0 | 0 | ce8cc1ee | 0 |
| k8s-drain | MARKDOWN | 9 | 3 | 0 | 0 | 0 | 13182cbb | 0 |
| nb-qt01 | ISO_PROCEDURE | 42 | 4 | 1 | 0 | 14 | 6bfa7650 | 0 |
| nb-qt02 | ISO_PROCEDURE | 20 | 3 | 0 | 1 | 7 | 916dc5f6 | 0 |
| nb-qt03 | ISO_PROCEDURE | 24 | 1 | 0 | 0 | 12 | dee5c74b | 0 |
| nb-qt04 | ISO_PROCEDURE | 13 | 1 | 0 | 0 | 6 | 44aa6282 | 0 |
| nb-thanhtra06 | ISO_PROCEDURE | 33 | 2 | 0 | 1 | 2 | 36a4efeb | 0 |
| nci-bdp-deviations | ISO_PROCEDURE | 38 | 6 | 0 | 0 | 0 | a0002f30 | 0 |
| nci-bdp-labeling | ISO_PROCEDURE | 12 | 0 | 0 | 0 | 0 | d55cc7a9 | 0 |
| nd30 | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| tb-qt01 | ISO_PROCEDURE | 22 | 1 | 0 | 1 | 2 | 325ba3a2 | 0 |
| tb-qt03 | ISO_PROCEDURE | 32 | 5 | 0 | 1 | 5 | dc781cc9 | 0 |
| tb-qt05 | ISO_PROCEDURE | 20 | 1 | 0 | 1 | 6 | eebd5f78 | 0 |
| vn-cv10065 | PROSE | 2 | 0 | 0 | 0 | 0 | 51da260f | 0 |
| vn-nq311-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-nq424-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-nq432-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-qd1308 | LEGAL_ARTICLES | 43 | 2 | 0 | 0 | 0 | 0875c136 | 0 |
| vn-qd82 | LEGAL_ARTICLES | 3 | 1 | 0 | 0 | 0 | df5d0071 | 0 |
| vn-tb425 | MARKDOWN | 5 | 0 | 0 | 0 | 0 | 55733f77 | 0 |
| vn-vbhn109 | LEGAL_ARTICLES | 34 | 1 | 0 | 0 | 0 | 7e6cb72a | 0 |

Invariants: offsets=0, substring=0, procedure_row=0, page_order=0, page_source=0, multi_page_table=0, token_budget=0.

Hard conditions: the 4 scans fail with `NO_TEXT_LAYER`; every family is unchanged; every `md sha` equals the baseline (the stored Markdown did not change, so `NORMALIZER_VERSION` stays); 0 invariant violations.

Deltas against the baseline:
- `uncovered` rose by design in 5 files, all table of contents lines now outside every chunk (snippets in `eval/results/pilot-chunks/phase-a.json`): `epa-qc` +3 ("1. General Information ____", "2. Field Sampling …", "3. Quality Control Samples …"), `nb-thanhtra06` +1 ("SỬA ĐỔI TÀI LIỆU"), `tb-qt01`, `tb-qt03`, `tb-qt05` +1 each ("BẢNG THEO DÕI SỬA ĐỔI TÀI LIỆU DANH SÁCH PHÂN PHỐI TÀI LIỆU"). The other uncovered body element (`nb-qt02`, a table) is the same as in the baseline. The column cannot tell an intended drop from a loss by itself; the snippets do.
- `tb-qt05`: the table of contents chunk is gone; chunk #0 is now the distribution list alone (187 tokens), chunk #1 starts at "1. MỤC ĐÍCH". Same count (20) because the distribution list is no longer folded into the contents chunk.
- `vn-vbhn109` 37 → 34 chunks, `<64` 3 → 1: "Số:", "/2026/VBHN-NĐ-NHNN" and the three false headings ("1 Nghị định số 366/… như sau:", "2. … bãi bỏ toàn bộ các Nghị định:", "3. … bãi bỏ một phần các Nghị định:") are body text again; the preamble is one 122-token chunk. The one left under 64 tokens is "Hà Nội, ngày tháng năm 2026" after the last article (not preamble; out of 5a).
- `vn-qd1308` 44 → 43 and `vn-qd82` 5 → 3: the underscore lines and the date line merged into the preamble chunk; `no letters` 1 → 0 in both.
- `epa-qc` 54 → 54, `<64` 1 → 2: the table of contents is only partly dropped. Its first entries are body lines under "TABLE OF CONTENTS" (dropped), but the entry "4. Internal Quality Control Procedures ____ 18" is a lone `list_item` that the outline promotes to a heading (`_is_lone_numbered_title`) and that has the paragraphs "References ____ 22" and "Revision History ____" as body, so the contents run ends there and that tail stays one 46-token chunk (before: one 85-token contents chunk). Known limit: the goal "no chunk is a table of contents" is not fully met for `epa-qc`.
- `tb-qt01`, `tb-qt03`: only the contents chunk changed (it became the distribution-list chunk, as in `tb-qt05`).
- `nb-qt03`, `nci-bdp-labeling`: no chunk changed. The `":"` rule rejects numbered **paragraphs** only: Docling reports real sub-headings such as `tb-qt01` "5.1 Kiểm soát tài liệu:" and `nb-qt03` "6.1 Các kết quả đạt được:" as `list_item`, and a first version of the rule that also rejected list items removed them from the outline (review round 2). Trade-off: `nci-bdp-labeling` lead-ins like "4.4 Label each raw material with:" stay headings, as before V2-47.
- Compared chunk by chunk with the `HEAD` chunker for `tb-qt01`, `nb-qt03`, `tb-qt03`, `nci-bdp-labeling`, `vn-vbhn109`, `epa-qc` (scratch script, old and new code on the same rendered documents).
- `nb-qt01` keeps one letterless chunk (ISO family, a decorative line; item 5b).

`reindex --all --dry-run` (run in the `sopilot-v2-ai-service` container, the host has no service env): `reindex_done dry_run=True found=25 queued=0`, 25 `reindex_candidate` lines. The chunker change is not seen by the stale check (`admin.py:6`); the owner reindexes with `--all` after merge (not done by this ticket).

Phase A gate (final code, 2026-11-22): `validate-build.ps1 -Scope ai` passed; ai-service unit 734 passed, 1 skipped, 15 xfailed (baseline at `f2995f3`: 706 passed); integration 158 passed; `validate-build.ps1 -Scope web` passed (build, lint, 240 Vitest); `cd eval; uv run pytest -q` 200 passed; corpus table above re-run on the final code. The frontend half of item 6 (`lib/viewer/report-labels.ts` and its test) is in the working tree only: `report-labels.ts` belongs to the uncommitted V2-46 frontend and is committed with it.

Review (fresh `v2-reviewer`, two rounds, no BLOCKER). Round 1, accepted and fixed: legal copy claimed "one chunk per article" for body-line articles (now "per article heading"); the `":"` rule hit converter headings; `gap_after` and chunk-slice invariants untested; a numbered "6. Contents" kit list was dropped (numbering no longer stripped); doc qualifiers. Round 2, accepted and fixed: the `":"` rule hit real list-item sub-headings (now paragraphs only); two negative tests (procedure table in the preamble, barrier after an absorbed section); §5.4 wording. Left open: the `epa-qc` contents tail (above); the V2-46 wireframe `docs/architecture/diagrams/ingest-strategy-preview.*` and its generator still say "never merged" for `LEGAL_ARTICLES` (untracked V2-46 files, regenerate with the V2-46 frontend); a converter heading like "1 PURPOSE" without a dot is no longer lifted under a roman heading (no corpus case); the processing report of a document ingested before V2-47 recomputes `signals` with the new outline rules.
