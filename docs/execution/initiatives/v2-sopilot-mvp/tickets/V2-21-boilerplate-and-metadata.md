---
id: V2-21
title: "ai-service: boilerplate separation, SOP metadata extraction and extraction warnings"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-09, V2-16, V2-25, V2-28]
branch: "feat/ai-qa-boilerplate-metadata"
assignee: pair
---

# TICKET V2-21: Strip the frame, keep the content

> Translated from Vietnamese on 2026-11-13; content unchanged. Quoted strings from source documents stay in Vietnamese.

## 1. Context & goal
[AUDIT-ingestion-sop-data](../../../../research/audit-ingestion-sop-data-2026-10-19.md) steps 4 and 8, PRD-V2 FR-08. The boilerplate (repeated headers/footers, national motto/heading lines, signatures, distribution lists, approval tables, revision tables) is being embedded as content. Remove it from the index but keep the useful information as metadata.

## 2. Acceptance criteria
- [x] Detect headers/footers repeated across PDF pages (DOCX deferred after the MVP per FR-06); remove them from content. Changed 2026-10-21 (audit by query type, owner decision P0-4, TECH-V2-ai-service §5.3): the "≥ 60% of pages" rule applies only when the PDF has at least `SOPILOT_HEADER_FOOTER_MIN_PAGES` pages (default 3, fixed on the V2-19 corpus), and the first `heading` element is never marked `header`; add 1-page and 2-page PDF fixtures, on which the "content wrongly removed" metric must be 0. *Done 2026-10-26: `docproc/clean/boilerplate.py`, tests in `test_clean.py` (including 1–2-page PDFs not losing content and the first heading not marked `header`) and the real PDF `framed_procedure` in `test_pdf.py`.*
- [x] Recognize national motto/heading blocks, number/reference code, distribution lists, signature blocks, Drafted/Reviewed/Approved tables and revision-tracking tables; remove them from the chunked content. *Done 2026-10-26 (VI/EN rules, synthetic tests).*
- [x] Extract metadata when present: document code, issue number, issue/effective date, approver. *Done 2026-10-26: `clean/metadata.py` returns `docCode`, `revisionLabel`, `issueDate`, `effectiveDate`, `approvedBy`. Scope changed 2026-11-01 (owner): "stored per document version" (`extracted_meta`) moved to `V2-09` because the `rag` tables belong to that ticket; see V2-09's `extracted_documents` criterion.*
- [x] Removed blocks have the form `{kind, page, text}` and never appear in the canonical Markdown, chunks or index (tested on fixtures with repeated headers/footers and approval tables). *Done 2026-10-26: `CleanResult.boilerplate` and a test that boilerplate blocks do not enter the Markdown. Scope changed 2026-11-01 (owner): the `extracted_documents.boilerplate` column is written by `V2-09` (already in V2-09's criteria); listing removed blocks in the FR-31 view is UI work (`V2-15`/`V2-31`), not this ticket.*
- [x] Warnings per TECH-V2-ai-service §5.3a (`PAGES_WITHOUT_TEXT`, `UNMAPPED_GLYPHS`, `NO_HEADINGS_DETECTED`, `BOILERPLATE_REMOVED`, `CONVERTER_WARNING` if the library has it): each code has a fixture that produces it and a clean fixture that does not; no aggregate confidence score; warnings never cause `FAILED`. *Done 2026-10-26: `clean/warnings.py`; each code has a producing fixture and a clean fixture producing no code.*
- [x] Never delete real content: on the V2-19 corpus, report the boilerplate leakage rate and the wrongful removal rate; the owner sets the thresholds. *Reporting done 2026-11-03 (section "Measured on the V2-19 corpus 2026-11-03" below): leakage 29.9%, wrongful removal 4.7%. **Thresholds pending the owner**; at current numbers both rates are still high for the Vietnamese ISO family, see the recorded bugs. After the 2026-11-04 fixes (section "Fixes and re-measurement 2026-11-04"): leakage 8.1% (VI 13.8%, EN 2.2%), wrongful removal 1.6% (11/706, all English revision-history tables labelled as content; 0 under the owner's convention). **Thresholds still pending the owner.***

## 3. Guide
- A processing step on V2-20's structure, before V2-22's chunking.
- Metadata schema per TECH-V2; if columns are added, a migration in `infrastructure/db/migrations/` and an update of `.agent/context/database/` (now `docs/architecture/data/`).

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | Repeated headers/footers; national motto blocks; approval tables; extracting document code and issue number | `uv run pytest tests/unit` |
| Eval | Scored on the V2-19 corpus | per V2-19 |

### Implementation notes 2026-10-26
Code: `services/ai-service/src/sopilot_ai/docproc/clean/` (`clean_document` sets `role` without deleting elements; `render` drops non-content elements). Configured through `CleanConfig` (`SOPILOT_HEADER_FOOTER_MIN_PAGES`=3, `SOPILOT_PAGE_MIN_CHARS`=20 are starting values, not calibrated on the real corpus). The boilerplate rules are written for VI/EN texts and checked only with self-made fixtures; not yet run on real documents. Kept `review` because three criteria above have no evidence yet.

### Measured on the V2-19 corpus 2026-11-03
Run: `predict_extraction.py --clean` (one Docling pass per file, ai-service venv, CPU, `HF_HUB_OFFLINE=1`) writes `eval/results/extraction-clean/predictions.{raw,clean}.jsonl` and `structured/*.json`; scored with `python -m sopilot_eval.cleaning` (from `eval/`) into `eval/results/extraction-clean/score.cleaning.json` (gitignored: contains document text). Scope: 21 files with text (19 PDFs + 2 Markdown); 4 rejection fixtures (`nd30`, 3 scans) not scored. Unit tests: `eval/tests/test_cleaning.py`.

**Definitions** (details in the `eval/sopilot_eval/cleaning.py` docstring). "Present" = the label's text, after normalization (NFC, casefold, collapsed whitespace, `|`, Markdown `#` and `---` lines removed), appears in the Markdown **of exactly the page** the label records (Markdown: the whole file), not glued to a preceding/following letter/digit.
- Leakage = the number of gold `furniture` blocks still present after cleaning / total gold `furniture` blocks.
- Wrongful removal = the number of gold content units (gold headings, non-empty column headers of gold tables) present before cleaning but missing after / the number of units present before cleaning. Units missing from the start (V2-20 extraction errors) are not in the denominator.
- Checking removed blocks: each removed `boilerplate` block is "confirmed" when it and a gold `furniture` block on the same page contain each other; otherwise "unconfirmed", listed for manual review.

| Group | Gold boilerplate | Present before cleaning | **Leakage** | Content units present | **Wrongful removal** |
|---|---:|---:|---:|---:|---:|
| Total (21 files) | 827 | 343 (41.5%) | **247 (29.9%)** | 706 | **33 (4.7%)** |
| lang=vi | 419 | 248 | 201 (48.0%) | 437 | 22 (5.0%) |
| lang=en | 408 | 95 | 46 (11.3%) | 269 | 11 (4.1%) |
| iso_9001 / vi (8) | 391 | 227 | 188 (48.1%) | 404 | 22 (5.4%) |
| administrative / vi (2) | 12 | 9 | 6 (50.0%) | 31 | 0 |
| non_standard / vi (3) | 16 | 12 | 7 (43.8%) | 2 | 0 |
| epa_sop / en (3) | 276 | 0 | 0 (0%) | 155 | 7 (4.5%) |
| fda_sop / en (1) | 36 | 27 | 3 (8.3%) | 32 | 4 (12.5%) |
| gmp_sop / en (2) | 88 | 64 | 39 (44.3%) | 53 | 0 |
| wiki_markdown / en (2) | 8 | 4 | 4 (50.0%) | 29 | 0 |

Notes on the numbers: "before cleaning" is already after Docling's furniture layer (`page_header`/`page_footer` are not rendered), so EPA's 0% leakage is thanks to Docling, not `clean_document`. The scorer's old metric (exact match on the whole document, `score_document`) gives 31.7% leakage. 508 blocks removed: 438 confirmed, 70 unconfirmed (6,271 characters, 4,896 of them in three EPA revision-history tables).

**Wrongful removal, case by case (33 units, 7 tables):**
- Real wrongful removals (VI, 22 units, 3 content tables): `nb-qt01` p. 11, the document list table (STT, Tên tài liệu, Mã số, Lần ban hành, Ngày ban hành, 1–6, Nơi nhận, Ngày nhận, Người nhận) and p. 13, the external documents table (STT, Tên tài liệu, Mã số/ký hiệu, Nơi ban hành, Ngày tháng năm ban hành, Nơi lưu) marked `revision_table`; `tb-qt01` p. 5, the assignment-by-document-type table (TT, Loại tài liệu, Biên soạn, Soát xét, Phê duyệt) marked `approval_table`.
- Label/convention conflicts (EN, 11 units, 4 tables): the "Revision History" tables (`epa-qc` p. 23, `epa-sw` p. 18, with the "Revision History" heading; `epa-soil` p. 28) and the version-history table of `fda-qms-sop` p. 9. The code removes them under the convention "revision tables are boilerplate" (pilot README, convention 2), while the gold labels record them as content tables/headings. **The owner decides** whether the label or the convention is right; if the convention is right, English wrongful removal = 0 and the labels need fixing (not fixed in this measurement round).

**Leakage, main causes** (the full list is `cases.leaked` in the results file):
- Vietnamese ISO (188/247): page headers ("SỞ XÂY DỰNG", "Mã hiệu: QT-01", "Lần ban hành 01", "Ngày ban hành: …", the procedure name) are returned by Docling as content **tables** at the top of the page; for example `nb-qt01` p. 3 `[["Mã hiệu:", "QT-01"], ["Lần ban hành", "01"], ["Ngày ban hành:", "05/11/2020"]]`. Most: `tb-qt05` 31, `nb-qt01` 28, `nb-thanhtra06` 28, `tb-qt03` 26.
- English GMP: `nci-bdp-deviations` "SOP Number: 21301" (17 pages), "Revision: 07" (16); `nci-bdp-labeling` "SOP 12188 Rev. 05" (4).
- Vietnamese administrative / non-standard: national motto/heading lines (`vn-qd1308`, `vn-cv10065`, `vn-tb425` p. 1), "Nơi nhận:" (distribution, 5 files), "KT. BỘ TRƯỞNG…" (`vn-tb425`).
- Markdown: HTML comments `<!-- overview -->`, `<!-- steps -->`, `<!-- body -->` (k8s).

**Unconfirmed removed blocks** (70; not gold content): bare page numbers ("2", "3"… in `vn-vbhn109`, `vn-qd1308`, `tb-qt03`, `vn-cv10065`, `vn-qd82`, `vn-tb425`), footer form codes `BM.QT.03.0x` (`tb-qt03` pp. 9–13), "SOP Title:" (`nci-bdp-deviations`, 17 pages), "Số: …" (`vn-qd1308`, `vn-cv10065`, `vn-qd82`; not in the `furniture` labels), signer names (`vn-qd1308`, `vn-cv10065`), revision table titles (6), the "Phê duyệt" footer of `nb-qt02` p. 10 (needs manual review), and the tables listed under wrongful removal.

**docproc bugs revealed (reported only, not fixed):**
1. `clean/boilerplate.py` `mark_repeated_header_footer` considers only `paragraph/heading/list_item`, so table-shaped page headers (Vietnamese ISO) are never marked `header`. Proposal: bring tables at the page edge into the repetition rule (repetition key on the table text, masking numbers), or mark as boilerplate tables whose every row matches `_DOC_NUMBER`/`_DOC_META_LINE`.
2. Same function: `_EDGE_ELEMENTS = 2`, while the NCI header is 7 elements per page (title, "SOP Title:", value, "SOP Number:", "21301", "Revision:", "07"), so only "SOP Title:" is removed. Proposal: an edge window by position (bbox) or by label–value groups, not a fixed element count.
3. `mark_frame_blocks`: Docling returns the national motto/heading lines as a `heading` (usually the first heading), and the `first_heading` protection blocks marking it as boilerplate; a motto inside a table (`vn-tb425`) is skipped because the rule skips tables. `_mark_recipients` accepts only `paragraph/list_item`, while "Nơi nhận:" comes out as a `heading`. Proposal: a first heading matching `_MOTTO` is not protected; the distribution rule also accepts `heading`; consider table cells at the top of page 1.
4. `is_revision_table` matches headers with "ban hành" + "ngày" and `is_approval_table` matches "Biên soạn/Soát xét/Phê duyệt" on **any** page, so content tables with those columns are removed (the 3 Vietnamese tables above). Proposal: require a position signal (first/last page, right after a "theo dõi sửa đổi" title) or characteristic columns ("nội dung sửa đổi", "lần sửa").
5. Markdown: no rule for HTML comments yet; proposal: drop `<!-- … -->` when extracting MD.

**Limits:** substring matching means a heading repeated in a table of contents on the same page hides its removal; very short labels ("2/9") can match wrongly; paragraphs have no gold labels, so wrongful removal is measured only on headings and column headers; 81 gold ISO units are missing before cleaning (V2-20 extraction errors) and cannot be measured; the labels were reviewed by an agent by delegation and not all re-read by the owner. **Thresholds pending the owner.**

### Fixes and re-measurement 2026-11-04
Fixed bugs 1–4 of the section above (bug 5, HTML comments in Markdown, not done). Code: `docproc/clean/boilerplate.py`, `docproc/clean/metadata.py`, `docproc/clean/model.py`, `docproc/clean/__init__.py`, and the new `docproc/tables.py` (table joining, see V2-22). The rules are structural, not based on file names or corpus-specific strings:
- Repeated headers/footers: the repetition key is computed on elements among the first/last 10 of the page (numbers masked, **leading section numbers kept** so "1.1 General" and "2.1 General" do not become one repeated line; "Label: value" lines get an extra key by label). A page's frame is the **run of consecutive repeated elements from the page edge inward**, of any length (the NCI header is 7 elements), stopping at the first non-repeated element (repeated lines in the middle of the body stay). A table of ≤ 6 rows with short cells is boilerplate when ≥ 60% of its non-empty cells repeat (keys by cell and by adjacent cell pairs in a row, because Docling cuts the same header differently across pages), every row with text has a repeated cell, and non-repeated cells are ≤ 60 characters (body tables with column headers repeated on every page fail this because of their data rows).
- Repetition threshold: `max(SOPILOT_HEADER_FOOTER_MIN_PAGES, header_footer_ratio × page count)`, **`header_footer_ratio` changed 0.6 → 0.4** (a starting value, pending the owner; TECH-V2-ai-service §5.3 still says 60%, not yet edited). Reason: ISO SOPs have form appendices with their own frame, so the main header covers only 41–57% of pages (`nb-thanhtra06` 7/17, `nb-qt01` 8/14); the most repeated content key at the page edge on the corpus covers ≤ 20% of pages. With 0.6 and every other fix: leakage 19.8% (ISO 39.1%).
- National motto/heading lines as the first heading are still marked boilerplate (the first-heading protection keeps only the title); a table at the top of page 1 containing the motto (short cells, ≤ 6 rows) is boilerplate; the title of a revision table right before the table is not protected either.
- "Nơi nhận:" as a heading (the colon is required, so a "Distribution" heading in the body stays); signature openings "KT./TM./TL./TUQ." as headings.
- Approval tables also need sign-off row/column labels (Họ tên, Chữ ký, Chức vụ, Ngày, Name, Signature, Date…) or must be a grid of ≤ 3 rows without sequence numbers; revision tables need a **first column** naming the revision ("sửa đổi", "revision", "history", "change", "rev") plus a date/content column; "ban hành" alone is no longer enough (that is a document register).
- Metadata also reads the rows of the header table marked as boilerplate ("Mã hiệu: QT-02").

New tests (synthetic, no Docling): `services/ai-service/tests/unit/test_clean_corpus_fixes.py`, 8 tests (at least one per bug). `run-tests.ps1 -Scope ai-service -Type unit`: 104 passed (96 old + 8); `validate-build.ps1 -Scope ai`: pass; `eval` `pytest tests`: 70 passed.

Re-measured: reusing `structured/*.json` (no Docling run: `extract/pdf.py` only changes how the table-joining function is called, extraction behaviour unchanged), `predict_extraction.py --clean --reuse-structured` then `python -m sopilot_eval.cleaning`; results overwrite `eval/results/extraction-clean/{predictions.*.jsonl,score.cleaning.json}`.

| Group | Leakage before | **Leakage after** | Wrongful removal before | **Wrongful removal after** |
|---|---:|---:|---:|---:|
| Total (21 files) | 247/827 (29.9%) | **67 (8.1%)** | 33/706 (4.7%) | **11 (1.6%)** |
| lang=vi | 201/419 (48.0%) | 58 (13.8%) | 22/437 | 0 |
| lang=en | 46/408 (11.3%) | 9 (2.2%) | 11/269 | 11 |
| iso_9001 / vi | 188/391 (48.1%) | 56 (14.3%) | 22/404 | 0 |
| administrative / vi | 6/12 | 2 | 0 | 0 |
| non_standard / vi | 7/16 | 0 | 0 | 0 |
| epa_sop / en | 0/276 | 0 | 7/155 | 7 |
| fda_sop / en | 3/36 | 3 | 4/32 | 4 |
| gmp_sop / en | 39/88 (44.3%) | 2 (2.3%) | 0 | 0 |
| wiki_markdown / en | 4/8 | 4 | 0 | 0 |

The old whole-document metric: 31.7% → 15.8%. Removed blocks 508 → 824 (confirmed 438 → 648, unconfirmed 70 → 176, 8,239 characters). The new unconfirmed blocks were reviewed by hand: all are boilerplate whose strings differ from the gold labels (the header line "Lần ban hành QT.01" with words reordered by Docling, the NCI SOP title repeated in each page header, list items under "Nơi nhận:" where the label records only the label line, page numbers, footer form codes `BM-xx`, FDA's "Title:"); no body paragraph seen. Metadata improved: `nb-qt01..04` have `docCode`/`revisionLabel`/`issueDate`, `nb-thanhtra06` and `tb-qt*` have `issueDate`, `fda-qms-sop` has `docCode`.

**The remaining wrongful removals (11, EN) are all label disagreements, not code bugs:** the "Revision History"/"History | Effective Date" tables of `epa-qc` p. 23 (heading + 2 column headers), `epa-sw` p. 18 (3), `epa-soil` p. 28 (1), the version-history table of `fda-qms-sop` p. 9 (4). Under the owner's convention, revision-tracking tables are boilerplate; the gold labels need fixing (not fixed in this round). Under the convention: real wrongful removal = 0/706.

**Remaining leakage (67):** header text cut differently by Docling, so the repetition key appears on fewer pages than the threshold (`nb-qt01` pp. 2/3/5 "SỞ XÂY DỰNG…", the `tb-qt05` header table on pp. 5/7/8/9 with only 2/6 cells repeating, the `fda-qms-sop` p. 4 header as lines instead of a table); the document's first heading kept as the title (`nb-thanhtra06`, `tb-qt01` p. 1); the national motto of appendix forms on pages ≠ 1 (`tb-qt03` pp. 9–12); "VĂN BẢN HỢP NHẤT" (consolidated text, `vn-vbhn109`); Markdown HTML comments (bug 5, not done); partly wrong substring matches by the scorer ("CẢNG VỤ HÀNG HẢI" appears in a body sentence of `tb-qt01`, `tb-qt03`). **Thresholds pending the owner.**

### Owner sets thresholds and closes the ticket 2026-11-04
The owner accepted the recommendation: `header_footer_ratio` = 0.4 (TECH §5.3 edited the same day). V2-21 acceptance thresholds: **leakage ≤ 10%** and **wrongful removal ≤ 2%** on the V2-19 corpus. Post-fix measurements: leakage **8.1%** (met), wrongful removal **1.6%** (met; all of it label disagreements over revision-history tables, 0 real errors). Known limitation: Vietnamese leakage **13.8%** (above 10%), because Docling cuts headers differently across pages; tracked in V2-07. A sample check of the 176 removed blocks the labels do not confirm: running headers, page numbers, footers, "Nơi nhận" lists, signatures, document numbers, revision-history tables; the random sample showed no real content. The 10%/2% thresholds were proposed by the assistant, not derived from their effect on retrieval. Evidence: `validate-build.ps1 -Scope ai` green, 104 ai-service tests and 70 eval tests pass (2026-11-04). Closed `done`.
