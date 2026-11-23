---
id: V2-47
title: "ai-service: chunk quality fixes found on the pilot corpus (false headings, letterhead tables, split step rows, table of contents, tiny legal fragments)"
type: fix
status: review # todo | in_progress | review | done | blocked
created: 2026-11-22
updated: 2026-11-23
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
  - **Decided by the owner 2026-11-22: neither.** The eval results already submitted stay as they are (measured with the old chunker and Markdown, item 9). `sop-main` / `sop-main-v3` are not re-frozen and no docproc commit is pinned. After Phase B, the docproc mode of the eval harness (`docproc_chunks.py`) refuses the frozen corpus at HEAD by design; any later eval result lives only in the repository and starts with a new freeze. The goal of the rest of this ticket is a correct, explainable pipeline for the demo.
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
| `services/ai-service/src/sopilot_ai/docproc/{model,render}.py`, `chunk/{headings,chunker,family}.py`, `ingest/pipeline.py`, `api/processing_report.py`, `tests/unit/test_markdown_headings_are_explicit.py`, `mock_docs/{families,gitlab-handbook}/` | MODIFY / CREATE (Markdown headings, section 7) |

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

Phase A review (fresh `v2-reviewer`, two rounds, no BLOCKER). Round 1, accepted and fixed: legal copy claimed "one chunk per article" for body-line articles (now "per article heading"); the `":"` rule hit converter headings; `gap_after` and chunk-slice invariants untested; a numbered "6. Contents" kit list was dropped (numbering no longer stripped); doc qualifiers. Round 2, accepted and fixed: the `":"` rule hit real list-item sub-headings (now paragraphs only); two negative tests (procedure table in the preamble, barrier after an absorbed section); §5.4 wording. Left open: the `epa-qc` contents tail (above); the V2-46 wireframe `docs/architecture/diagrams/ingest-strategy-preview.*` and its generator still say "never merged" for `LEGAL_ARTICLES` (untracked V2-46 files, regenerate with the V2-46 frontend); a converter heading like "1 PURPOSE" without a dot is no longer lifted under a roman heading (no corpus case); the processing report of a document ingested before V2-47 recomputes `signals` with the new outline rules.

### Phase B (2026-11-22, working tree on `fix/ai-chunk-quality`)

Code: `docproc/clean/boilerplate.py` (items 2 and 5b), `docproc/tables.py` (item 3), `docproc/render.py` (item 8); tests `tests/unit/test_clean_v2_47.py`, `tests/unit/test_tables_v2_47.py`, `tests/integration/test_retrieval.py::test_a_version_cleaned_by_an_older_normalizer_is_stale`; TECH-V2-ai-service §5.2, §5.3, §5.4; TEST-REPORT-005 section 8; V2-18 section 2b.

**Item 2, failing condition.** `tb-qt05` has 11 pages, so the repeat rule needs `max(3, 0.4 x 11) = 4.4` pages. The letterhead is a 3x4 table, `header_rows=0`, **identical** on pages 5, 7, 8, 9 (the ticket's "text split differently per page" holds for the pages where Docling returned it as lines, which were already marked): its cells repeat at a page edge on 4 pages, under 4.4. Shape, `_EDGE_WINDOW`, `_MAX_FRAME_LABEL` and the rows-hit rule all pass. Change: a small table whose whole grid (shape and exact folded text of its non-empty cells, digits included; review: masking digits would have removed small value tables that differ only in numbers) is identical at a page edge on at least `header_footer_min_pages` (3) pages is header/footer; the 0.4 ratio is unchanged for lines and for the cell-share rule. Side effect fixed: the page-9 letterhead was being joined onto the "7. HỒ SƠ" records table (same width, next page).

**Item 3.** With the letterhead marked, the existing join links pages 4, 5, 6. The rest needed two new join cases and stitching (`tables.py`, cleaning only; the extractor's join is unchanged): a next-page part whose first row is a continuation row (first two cells empty, text after them) joins even when Docling marked that row as a header, or when the part is exactly one column narrower (Docling dropped the empty trailing "Biểu mẫu" column on page 7; padded on the right). The continuation row is stitched into the previous last row (text appended in the same column) and keeps that row's page, so a step chunk keeps the page it starts on; `cell_spans` shift by the rows not appended, a span on the stitched row moves down one row with one row less (dropped when its rowspan is 1); `row_spans` are computed by the renderer afterwards (asserted in order and inside the table). A row with an empty number but a filled second cell is a new step. **Cause of `Cột N`:** the page-7 part stayed a separate table (width 4, `header_rows=1`), passed `is_procedure_table` because its overflow "header" text contains "trách nhiệm" and "nội dung", and `step_rows` names columns with an empty header `Cột N`; joining it removes the cause. Result: one procedure table pages 4 to 8 with **8 whole steps** (the ticket expected 6; the document has 8), each labelled `TT | Hoạt động | Trách nhiệm | Yêu cầu | Biểu mẫu`.

**Item 5b.** Body paragraphs made only of `_ - = * ~ .` and spaces, at least 3 of them, are `boilerplate`, kind `decorative_line` (a lone `-` or `.` stays).

**Item 8.** `NORMALIZER_VERSION` 2 → 3 (`docproc/render.py:13`). The stale check reports versions with the old value: new integration test (`stale_versions` lists the version, `/health` is `degraded`, `reindex --dry-run` finds it). On the local stack, `reindex --dry-run` **without** `--all`: old code `reindex_done dry_run=True found=0 queued=0`; new code (normalizer 3, the branch's `src` and `config` copied into a temp folder of the running `sopilot-v2-ai-service` container, removed afterwards) `reindex_done dry_run=True found=25 queued=0`: all 25 active versions of the owner's data are stale until reindexed. Consequences: (a) `rag.message_citations` stores character offsets with a `version_id`; a reindex rewrites the Markdown of the same version, so highlights of earlier conversations can point at shifted text; (b) `/health` reports `degraded` until the owner runs `python -m sopilot_ai.admin reindex`; (c) **mismatch, not fixed here:** retrieval does not skip stale-normalizer chunks (`retrieval/search.py:39` filters only on embedding model and revision) although the comment at `api/app.py:45-46` says it does. Reindexing the owner's data is not done by this ticket.

| file | family | chunks | <64 | no letters | uncovered | steps | md sha | violations or failure |
|---|---|---|---|---|---|---|---|---|
| epa-qc | ISO_PROCEDURE | 54 | 2 | 0 | 3 | 0 | b71f13cc | 0 |
| epa-soil | ISO_PROCEDURE | 75 | 1 | 0 | 0 | 0 | 8a8601b9 | 0 |
| epa-sw | ISO_PROCEDURE | 42 | 0 | 0 | 0 | 0 | 8fa5f4c2 | 0 |
| fda-qms-sop | ISO_PROCEDURE | 22 | 1 | 0 | 0 | 0 | 768c5464 | 0 |
| k8s-disruptions | MARKDOWN | 16 | 2 | 0 | 0 | 0 | ce8cc1ee | 0 |
| k8s-drain | MARKDOWN | 9 | 3 | 0 | 0 | 0 | 13182cbb | 0 |
| nb-qt01 | ISO_PROCEDURE | 37 | 4 | 0 | 0 | 14 | 0c6c480b | 0 |
| nb-qt02 | ISO_PROCEDURE | 20 | 3 | 0 | 1 | 7 | 916dc5f6 | 0 |
| nb-qt03 | ISO_PROCEDURE | 23 | 1 | 0 | 0 | 12 | 264767c4 | 0 |
| nb-qt04 | ISO_PROCEDURE | 13 | 1 | 0 | 0 | 6 | 8f84742f | 0 |
| nb-thanhtra06 | ISO_PROCEDURE | 34 | 2 | 0 | 1 | 2 | d4e183ae | 0 |
| nci-bdp-deviations | ISO_PROCEDURE | 38 | 6 | 0 | 0 | 0 | a0002f30 | 0 |
| nci-bdp-labeling | ISO_PROCEDURE | 12 | 0 | 0 | 0 | 0 | d55cc7a9 | 0 |
| nd30 | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| tb-qt01 | ISO_PROCEDURE | 22 | 1 | 0 | 1 | 2 | 325ba3a2 | 0 |
| tb-qt03 | ISO_PROCEDURE | 32 | 5 | 0 | 1 | 5 | dc781cc9 | 0 |
| tb-qt05 | ISO_PROCEDURE | 16 | 1 | 0 | 1 | 8 | d9d43b34 | 0 |
| vn-cv10065 | PROSE | 2 | 0 | 0 | 0 | 0 | 5ba88f0c | 0 |
| vn-nq311-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-nq424-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-nq432-scan | - | - | - | - | - | - | - | extract:NO_TEXT_LAYER |
| vn-qd1308 | LEGAL_ARTICLES | 43 | 2 | 0 | 0 | 0 | 5ed56798 | 0 |
| vn-qd82 | LEGAL_ARTICLES | 3 | 1 | 0 | 0 | 0 | d0e6b4a0 | 0 |
| vn-tb425 | MARKDOWN | 5 | 0 | 0 | 0 | 0 | 55733f77 | 0 |
| vn-vbhn109 | LEGAL_ARTICLES | 34 | 1 | 0 | 0 | 0 | 7e6cb72a | 0 |

Invariants: offsets=0, substring=0, procedure_row=0, page_order=0, page_source=0, multi_page_table=0, token_budget=0. Families unchanged, the 4 scans fail with `NO_TEXT_LAYER`. The Markdown changed in 8 files (`md sha`), as expected. Removed blocks compared with the Phase A code on the same extraction (scratch worktree at `507e7ff`): every added block is a `decorative_line` (lines of underscores, dashes or dots in `nb-qt01`, `nb-qt03`, `nb-qt04`, `nb-thanhtra06`, `tb-qt05`, `vn-cv10065`, `vn-qd1308`, `vn-qd82`) or one of the four `tb-qt05` letterhead tables; no block was un-removed; only `tb-qt05` changed its steps (6 → 8). `nb-qt01` lost its last letterless chunk (a line of dots).

V2-21 limits re-measured on the V2-19 corpus (`predict_extraction.py --clean --reuse-structured`, `python -m sopilot_eval.cleaning`, into `eval/results/v2-47-clean-{base,phase-b}`): leakage 67/827 = **8.1% → 51/827 = 6.2%**; wrongful removal **11/706 = 1.6%, unchanged** (the same revision-history label disagreements); removed blocks 824 → 898, unconfirmed 176 → 246 (the decorative lines, which the labels do not list). Both within the limits (10%, 2%).

Phase B gate: `validate-build.ps1 -Scope ai` passed; ai-service unit 754 passed, 1 skipped, 15 xfailed (after the review fixes); integration 159 passed; `validate-build.ps1 -Scope web` passed (240 Vitest); `cd eval; uv run pytest -q` 200 passed. Eval docproc mode at HEAD: refuses the frozen `sop-main` corpus by design (section 2 decision), not run.

Phase B review (fresh `v2-reviewer`, one round, no BLOCKER; accepted and fixed): the whole-table key masked digits, so small value tables that differ only in numbers on 3 pages of a long document would be removed (now exact folded text, negative test); a merged cell starting on the stitched row lost its value (it now moves down with its value, asserted through `step_rows`); the two new join cases could join a next-page table whose header has blank corner cells (now the row must look like overflow text, negative tests); a lone `-` or `.` was a decorative line (now at least 3 characters); the item 8 evidence lacked a real dry-run (added above); the normalizer test now asserts the bumped value and restores the shared database in `finally`. After the fixes the corpus table, the removed blocks and the V2-21 numbers are unchanged (re-run). Left open: a narrower part is padded on the right, so a part from which Docling dropped a middle column would shift (none in the corpus); a decorative line between two table parts that is not a repeated footer still blocks their join (decorative lines are marked after joining); stitched text can fill a cell that an earlier merged cell covered; the letterhead gets the role `header`, not `boilerplate` as item 2 words it (it is still listed in the removed blocks and absent from the Markdown). F3 stays open.

### Markdown headings are explicit (2026-11-23, working tree on `fix/ai-chunk-quality`)

Found while reading the chunks of 10 real GitLab handbook pages (`mock_docs/gitlab-handbook/`): in `09-incident-management-on-call-index` the shift list `1. APAC 23:00 - 07:00` … `3. AMER 15:00 - 23:00` was promoted to level-1 headings, because `str.isupper()` ignores digits and punctuation (`headings.py`, the depth-1 branch of `_classify`), so 22 of 29 `section_path` values started with `3. AMER 15:00 - 23:00`. The numbering patterns exist for converter output (ADR-008 section 6.1: Docling returns almost every heading at level 1 and reports numbered titles as list items); Markdown has no such uncertainty.

**Change** (owner decision 2026-11-23): `resolve_outline(elements, file_type)` takes the file type. For `"MD"` no `paragraph` or `list_item` is promoted by pattern and the all-caps fallback is off; a heading is a `#` line only. PDF and an unknown type (default) are unchanged. The type travels as `RenderedDocument.file_type` (set by `render`), and `detect_family`, the chunker, `process_document` and the processing report pass it. Tests: `tests/unit/test_markdown_headings_are_explicit.py` (6, including the PDF controls). Unit suite 765 passed, 1 skipped, 15 xfailed; ruff clean.

**Evidence (offline, same `process_document` code, old rule against new rule on the same files):**
- 8 families files and the 10 handbook pages: identical chunks except `09` (29 → 28 chunks, the 22 wrong paths gone). The legal fixture `legal-vi-quyet-dinh-ban-hanh-quy-dinh-bao-mat.md` had no `#` and relied on the all-caps fallback (3 → 2 chunks, empty paths); its two title lines now start with `# `, which restores the previous 3 chunks.
- 300 random pages of the public handbook (4206 `.md` files listed through the GitLab API, seed 47): 291 processed (9 `EMPTY_CONTENT`, stubs, same before and after), 11 pages without any `#` heading, **the all-caps fallback fired on 0 pages**, 11 pages changed (chunks -3 to 0), 0 family changes. The 28 removed promotions: 13 list items (`1. CIO`, `2. MRARR`, `1. Opportunity.Net_ARR__c` …, 4 through the `isupper` path) and 15 bold lines such as `**1. Schema migrations**` that the old rule made level-1 headings (their real parent heading left the path); they are body text under the real parent now. The effect on retrieval ranking was not measured.
- PDF, 18 PDFs of the V2-19 pilot (cached `extract()` output in `eval/results/v2-47-clean-phase-b/structured`, 380 gold headings): heading text and page found 345, of which 321 (93%) have the right level; the 24 level misses are four document-specific patterns (`1.0 PURPOSE` read as depth 2, roman `I.`–`VI.` under a level-1 title, unnumbered sub-headings that Docling reports at level 1). The all-caps fallback fired on 1 PDF (`vn-cv10065`, no heading found by Docling) and promoted 0 lines. The `isupper` path promoted 28 list items on 4 PDFs (`nb-thanhtra06`, `tb-qt01`, `tb-qt03`, `tb-qt05`), all in the contents box on page 1 (none in the gold labels); `_drop_contents` removes that section, and the chunks (count, content, paths, family) are identical with and without those promotions.

**Decision (owner, 2026-11-23): PDF is left as it is.** Open risk, not fixed: a PDF with a numbered list of capitalised codes in the body (not in a contents box) would get the same false headings as handbook page 09; a "no list-item neighbour" check was tried offline and changed no chunk of the 4 PDFs, but the sample has no such body list, so it proves no benefit. Heading levels on PDF stay as measured (93%); the misses are not fixed because each is specific to one document.

**Not done:** reindex of the owner's data (chunks already stored keep the old paths until `reindex --all`; the owner runs it after merge, section 2). The retrieval effect of the changed paths is in the paragraph "Retrieval effect" below. The web and eval suites were not re-run for this change (no frontend, schema or eval file changed); the ai-service unit and integration suites run in `pre-commit-check.ps1`.

**List item that opens with `>` (2026-11-23, same day).** Found by asking "Can I expense a $6,000 marketing purchase through Navan?" on the handbook pages: the answer said "$5,000 or more" where the source says `>$5,000` (greater than). Trace: the source line `- >$5,000 needs to go through the procurement process in [Zip]` is a bullet holding a blockquote in CommonMark; `extract/markdown.py` skipped `blockquote_open` and, because the token after `list_item_open` was not a `paragraph_open`, emitted an empty `list_item` and then the quote's paragraph as a separate paragraph, without the `>`. Fix: when the first block of a list item is a blockquote, the item takes the quote's first paragraph and keeps the marker (`>` plus the spacing of the source line, read through the token's line map); a second paragraph of the quote is walked as before. A top-level blockquote is unchanged (marker dropped). Tests: `tests/unit/test_markdown_list_item_blockquote.py` (6). Unit suite 771 passed, 1 skipped, 15 xfailed; ruff clean. Old extractor (from `HEAD`) against new on 319 Markdown files (8 families, 10 handbook pages, 300 random handbook pages): 2 files differ, both the "greater than" case (`>$5,000` in `05-finance-expenses`, `>3 participants: 1 vote each` in a UX playbook page); the other empty list items in the old output (9 in total) come from other constructs and are untouched. The stored Markdown of such documents changes; `NORMALIZER_VERSION` stays `3` because version 3 is the unmerged V2-47 set and the owner's data is not reindexed yet. The test documents ingested on the working stack that day carried version 3 with the earlier extractor; they were deleted (see "Local database state").

**Verified on the running stack (2026-11-23).** After rebuilding `ai-worker`, `05-finance-expenses` uploaded to a new dev workspace stores chunk #54 as `- >$5,000 needs to go through the procurement process in Zip.` (the `>` kept; 79 chunks, family `ISO_PROCEDURE`), and "Can I expense a $6,000 marketing purchase through Navan?" answers "any amount greater than $5,000 must go through the procurement process in Zip" (before: "$5,000 or more"). The processing report of `09-incident-management-on-call-index` shows 30 headings after `ai-service` was rebuilt (33 before, because the API recomputes the outline with its own code). Three chat questions on the new chunks were answered correctly (AMER coverage 15:00–23:00 and the Thanksgiving plan; the $6,000 case; the 12-character / 180-day password rule of the Vietnamese legal fixture).

**HTML comments (2026-11-23).** `<!-- ... -->` is removed in blocks and inline (`extract/markdown.py`). Before, `02-people-group-offboarding-index` and `07-finance-procurement-index` began with a comment-only paragraph (`<!-- markdownlint-disable MD051 -->`, a 15-token chunk with no path) and `07` ended with its matching `enable` comment; 19 of 300 sampled handbook pages contain comments. Old extractor against new on 319 Markdown files: 22 differ, all by removed comments, usually 1 or 2 elements; the two large drops are pages whose template instructions sit in comments (a README template, a design-document template: 9 and 13 paragraphs of "Add 5-10 bullet points on…"). Tests: `tests/unit/test_markdown_html_comments.py` (5). Unit suite 776 passed, 1 skipped, 15 xfailed; ruff clean.

**Top-level blockquote with `>` glued to the text: not changed.** The same loss could happen for a paragraph that starts `>$5,000`. Across the 319 files there are 73 top-level blockquotes: 72 have a space after `>` (real quotes and callouts) and 1 is glued (`>Note: …`, also a real quote). No case reads as "greater than", so no rule was added; one would be a guess without evidence.

**Retrieval effect of the corrected paths (offline, 12 hand-written questions on the 10 handbook pages).** Hybrid retrieval as in the service (bge-m3, BM25, RRF k=60, no rerank), one index of the 10 pages, page `09` chunked with the old and with the new outline rule, rank of the chunk holding the answer: found 12/12 in both; top-1 10 → 12; mean reciprocal rank 0.88 → 1.00. The AMER coverage question went from rank 17 to 1 (the shift list had been turned into headings, so its text sat in `section_path` instead of the chunk body) and "which groups of team members are recommended" from 2 to 1. One page, 12 questions, no rerank: a sign, not a measurement of the whole corpus.

**Accepted limits, unchanged.** Merged sibling sections keep the first section's path (owner decision, option B), so an item merged into an earlier one is in the content but not in the path; this was the most frequent label mismatch in `05` and `07`. Raw HTML inside heading text and `{#anchor}` suffixes still appear in some paths.

**Local database state (2026-11-23).** All test uploads of this work (48 documents, 35 conversations in the dev workspaces `families-test` to `families-test4`) were deleted through the application API. Read-only counts afterwards: `core.documents` 0, `core.document_versions` 0, `rag.chunks` 0, `rag.extracted_documents` 0, `rag.ingestion_jobs` 0; every outbox event `DELIVERED` (core 96, rag 144, none dead); core migrations up to V012 and rag up to V004 applied; `/health` of ai-service `ok` (not `degraded`), core-api `UP`. The workspace of the owner holds no document, so there is nothing to reindex now; every document uploaded from here on is chunked by the new code. The earlier statement in Phase B that "all 25 active versions of the owner's data" were stale is not supported by the current database: the owner's workspace is empty, and the stale versions it counted were documents that no longer exist. A reindex is only needed again if documents ingested by older code are loaded later.

**Mock documents.** `mock_docs/families/` (8 files written for the family tests) and `mock_docs/gitlab-handbook/` (10 pages of the public GitLab handbook, source and note in its `README.md`) are committed so the checks above can be repeated.
