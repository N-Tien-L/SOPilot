---
id: ADR-008
title: "V2: use Docling as the extraction library for PDFs with a text layer"
status: approved
created: 2026-10-21
updated: 2026-11-13
author: "Owner"
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/architecture/components/ai-service.md
  - docs/03-plans/tickets/V2-20-structured-extraction.md
  - docs/04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md
deciders: ["Owner"]
amends: []
supersedes: []
superseded_by: ""
---

# ADR-008: Docling as the PDF extraction library

> **Status:** `approved` (2026-10-21) | **Decided:** `2026-10-21` | **Decider:** `Owner`
>
> **No spike measurements at decision time.** The decision rests on the official documentation read on 2026-10-21 and the owner's choice; Docling had not been tried on the V2-19 corpus, and speed, RAM and Vietnamese quality had not been measured. `V2-20` confirms the decision against the hard constraints in §4 and records real measurements in §6. If a hard constraint fails, this ADR returns to `draft` (§5).
>
> Translated from Vietnamese on 2026-11-13; section numbers are stable. Quoted strings from source PDFs stay in Vietnamese.

---

## 1. Context and the decision to make

- TECH-V2-ai-service §5.2 and PRD-V2 FR-08 require **one** library that converts PDFs with a text layer into a `StructuredDocument` (headings, paragraphs, lists, tables, real page numbers, reading order), from which ai-service renders the canonical Markdown with offsets. No plain-text extraction followed by rebuilding structure, no fallback chain, no OCR, no LLM rewriting.
- The [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md) report §6 named two candidates: **Docling** (MIT) and **PyMuPDF 2.x** (AGPL-3.0 or a commercial license), to be chosen by a 2-day spike in `V2-20`.
- On 2026-10-21 the owner chose Docling without waiting for the comparison spike.
- General constraints: runs locally on CPU (the owner's machine, 32 GB RAM), free, ai-service already needs `torch` for `bge-m3`, only PDFs with a text layer and Markdown in the MVP.

## 2. Evaluation criteria

From AUDIT-markdown-normalization §6.2:
1. Runs offline on CPU with models downloaded in advance; no network calls during processing.
2. OCR can be disabled completely, verifiably.
3. Every element has its real page number; headers/footers are separated, or there is enough page information for `V2-21` to separate them.
4. Vietnamese in NFC, no lost diacritics.
5. MIT/Apache/BSD licenses preferred; AGPL needs owner confirmation.
6. Added 2026-10-21 (audit by query type): returns merged-cell spans (`cell_spans`) so `PROCEDURE_STEP` chunks can repeat a merged cell's value down each row (TECH-V2-ai-service §5.2, §5.4).
7. Heading/table quality per document family, time and RAM per page, maintenance effort: comparable only once measured.

## 3. Options considered

### Option 1: Docling
- **Description:** `DoclingDocument` has a `body` tree and `furniture` (headers/footers separated from the body), per-element provenance, a layout model, reading order, TableFormer for tables (`FAST`/`ACCURATE`).
- **Pros (+):** MIT license; `furniture` supports `V2-21`; `artifacts_path` and `docling-tools models download` for offline use; thread-count and page-queue options to reduce RAM; the `torch` dependency overlaps with ai-service so the extra cost is smaller (an assessment, not measured).
- **Cons (-):** models download on first use and are heavier; OCR is an extra that must be disabled by configuration; the exact provenance field names, the `do_ocr` default, the Docker image size and Vietnamese quality were unverified.

### Option 2: PyMuPDF 2.x (with layout)
- **Description:** layout analysis without a GPU; `page_chunks` returns `page_boxes` with classes `section-header`, `table`, `page-header`, `page-footer`, `list-item`.
- **Pros (+):** lighter dependencies according to the publisher; a familiar API.
- **Cons (-):** AGPL-3.0 (or commercial) license, needing owner confirmation and carrying obligations if it is ever offered over a network; version 2.0 was released on 2026-10-19, so the API is new; OCR runs automatically if an engine is present and must be disabled.

### Excluded by scope (not a measured result)
Marker and MinerU (GPL/AGPL licenses or separate model terms, heavier than the target), `unstructured` (many dependencies, no better table structure according to the available documentation).

## 4. Decision and rationale

- **Chosen option: Option 1, Docling**, behind the adapter `services/ai-service/src/sopilot_ai/docproc/extract/pdf.py`. This is the only place that depends on the library; `V2-21` and `V2-22` work on `StructuredDocument`, so they are not bound to this choice.
- **Reasons:** (1) the MIT license needs no further legal decision, unlike AGPL; (2) `furniture` already separates headers/footers, matching `V2-21`'s boilerplate step; (3) offline configuration is built in; (4) the cost of the `torch` dependency is already in ai-service. Reason (4) and running on CPU within the time budget are **assessments, not measured**.
- **Mandatory configuration:** OCR disabled completely, with a test (an image-only page yields 0 characters and no OCR engine is called); models loaded from `SOPILOT_PDF_ARTIFACTS_PATH` (TECH-V2-ai-service §10), never downloaded during processing; thread and page-queue limits configurable; **the version is pinned** (the version read on 2026-10-21 was `docling 2.140.0`, released 2026-10-16; the official pinned version is recorded in §6 after `V2-20` installs and runs it).
- **Only one library** in the runtime: PyMuPDF is not used alongside it or as a fallback.

## 5. Conditions for revisiting (no spike measurements yet)

`V2-20` confirms Docling with these checks, on the minimum subset of `V2-19` (or synthetic fixtures labelled as synthetic if the corpus is not ready):

1. **Hard constraints** (criteria 1–5 in §2): if any fails, this ADR goes back to `draft` and `V2-20` stops to ask the owner; it does not switch libraries on its own.
2. **Merged-cell spans** (criterion 6): measured on tables with merged cells. If Docling returns no spans, `cell_spans = None`, the chunker does not guess values for empty cells, and the limitation is recorded in §6; this alone does not send the ADR back to `draft`.
3. **Time and RAM:** starting target (not yet based on measurements): extracting a 20-page PDF takes at most half of the NFR's 60 s budget, leaving room for embedding. A clear overrun is reported to the owner and may reopen the comparison with PyMuPDF 2.x (in which case AGPL needs owner confirmation, PLAN-V2 §4).
4. **Vietnamese heading/table quality** per document family: report the measurements, no threshold set in advance (AUDIT-markdown-normalization §6.2 item 6).

## 6. Confirmation results (filled in by V2-20)

| Item | Result | Date |
|---|---|---|
| Pinned Docling version | `docling==2.142.1` (`docling-core 2.104.0`), the `pdf` extra of `services/ai-service`. Models fetched once from HuggingFace on the owner's machine; offline operation uses `SOPILOT_PDF_ARTIFACTS_PATH` (that path has not been tested on its own) | 2026-10-26 |
| Offline CPU, models loaded from `artifacts_path` | Runs on CPU (`device=cpu`), no GPU. The `artifacts_path` setting is passed to the pipeline; 10 PDFs (148 pages) ran with `HF_HUB_OFFLINE=1`, models from the HuggingFace cache, without errors: no network needed during processing. **Not yet checked:** the `SOPILOT_PDF_ARTIFACTS_PATH` path with a folder downloaded by `docling-tools models download` (see §6.2) | 2026-10-26 |
| OCR off, image pages yield 0 characters | Passed on a synthetic fixture: `do_ocr=False`, an image-only page yields 0 characters, no OCR module is imported (`test_pdf.py`). A fully image-based PDF (NĐ 30, 76 pages) is stopped by the text-layer check: `NO_TEXT_LAYER` | 2026-10-26 |
| Real page numbers for every element; `furniture` or page info for `V2-21` | Passed: every element has `page`; `page_index` is consecutive. Docling separates `furniture` (headers/footers) into separate elements: 0–124 elements per file, kept with `role` header/footer/boilerplate for V2-21 | 2026-10-26 |
| NFC and Vietnamese diacritics on sample PDFs | Passed: 10/10 PDFs with text come out in NFC; the synthetic fixture has every tone mark and `đ`. 2 `U+FFFD` characters in `nb-qt03` (V2-21 emits `UNMAPPED_GLYPHS`) | 2026-10-26 |
| Merged-cell spans (`cell_spans`) | Docling **does return** `row_span`/`col_span`: 56 merged cells across 10 PDFs, in 49 tables with at least one merged cell. Accuracy against labels was not measured (the pilot labels were not yet approved by the owner). On a reportlab fixture with a vertical merge, Docling did **not** detect the span (it put the text in the next row, `row_span=1`): spans are not fully reliable | 2026-10-26 |
| Time and peak RAM per page on the owner's machine | AMD 16 threads, 33.6 GB, CPU, 4 Docling threads. 10 PDFs, 148 pages: 1.0 to 8.1 s/page (median about 3.4); peak process RAM 1.8 to 2.1 GB including models (per process, not per page). The starting target (≤ 30 s for 20 pages) is **not met for table-heavy documents** (`nb-qt01`: 8.1 s/page, 14 pages took 113 s) and is met for EPA (1.0 to 1.9 s/page). Not rerun to measure variance; the first run outside the model cache was not measured | 2026-10-26 |
| Headings and tables per document family (V2-19) | Scored on labels of selected pages (see §6.1): **heading text recall 96–100%, precision 64–88%; heading levels unusable** (Docling returns almost everything as level 1; scored with levels, recall is 65–69% VI, 57% EN); **table recall 40% VI, 0% EN**, precision 25% and 0%; merged cells 0/2 VI (22 predicted), 2/6 EN. Small sample (10 files, selected pages); labels reviewed by Claude on the owner's behalf, not yet re-read by the owner | 2026-10-26 |

### 6.1 Results on the selected-page labels (V2-20, 2026-10-26)

Source: `eval/predict_extraction.py` (the same `docproc` code as the service) and
`python -m sopilot_eval.extraction --selected-pages` on the 10 V2-19 PDFs; nd30 (scanned) is excluded from the scores
because of `NO_TEXT_LAYER`. Labels cover only the selected pages and were reviewed by Claude from page images on the owner's behalf
(`reviewer_id=claude-on-behalf-of-owner`); the owner has not re-read them. Exact match on normalized strings.
Raw results are in `eval/results/extraction-docling/` (not committed).

| Group | Headings, text + page only (P / R) | Headings, with level (P / R) | Tables (P / R) | Merged cells (matched / labelled / predicted) | Boilerplate leaked into content |
|---|---|---|---|---|---|
| VI, ISO 9001 (8 files) | 0.64 / 0.96 | 0.44 / 0.65 | 0.25 / 0.40 | 0 / 2 / 22 | 13 / 58 |
| EN, EPA (2 files) | 0.88 / 1.00 | 0.50 / 0.57 | 0.00 / 0.00 | 2 / 6 / 2 | 6 / 15 |

With the auxiliary rule "a list item with a short sequence number counts as a heading" (`docling+numbering`), VI text recall rises to 1.00 and
VI recall with levels to 0.69; EN is unchanged.

Observations (from reading predictions against labels, not statistics):
- **Flat heading levels:** Docling returns almost every heading at level 1 (for example `5.1.2.1` at level 1, labelled level 4). Levels must be inferred from the numbering in V2-22.
- **Extra headings:** page-header boilerplate (agency names, "QUY TRÌNH ...") and bold dash-led lines ("- Chương trình đánh giá:") are treated as headings, so VI precision is only 0.64.
- **Complex tables:** Docling does not separate nested tables. Page 4 of nb-qt01 comes out as one 8×7 table with 16 merged cells, while the labels have two tables (4×5 and a nested 4×5). Table-shaped page headers also become separate tables. The EPA information table comes out with 4 rows; the label has 6.
- **Merged cells cannot be used** to repeat values down each row in V2-22 without checks: the predicted set is large and matches the labels only for EPA.
- **Boilerplate leaks:** table-shaped headers inside the body are not yet separated; boilerplate removal is V2-21, so this figure is the pre-V2-21 baseline.
- **Metadata not measured** (belongs to V2-21).

Consequences for V2-21/V2-22: do not rely on Docling's heading levels or `cell_spans` without a separate inference layer and checks;
rules are needed for nested tables and table-shaped boilerplate. No acceptance threshold yet: the owner decides after seeing this baseline.


### 6.2 Configuration experiments and provisional thresholds (2026-10-26)

The same 10 PDFs, the same selected-page labels, run offline (`HF_HUB_OFFLINE=1`). One run per configuration; the run order is fixed, so the first run may include an extra cold start. Raw results are in `eval/results/extraction-exp/` (not committed).

| Configuration | Total time, 148 pages | s/page (median) | Peak RAM | Tables matching labels (gold 12) |
|---|---|---|---|---|
| default, 4 threads (`TableFormerMode.ACCURATE`, cell matching on) | 480 s | 3.2 (2.4) | 2191 MB | 4 |
| 4 threads, `do_cell_matching=False` | 407 s | 2.8 (3.5) | 2178 MB | 5 |
| 8 threads | 296 s | 2.0 (2.1) | 2201 MB | 4 |
| 12 threads | 253 s | 1.7 (2.0) | 2159 MB | 4 |
| 12 threads, TableFormer V2 (`SOPILOT_PDF_TABLE_MODEL=v2`) | 253 s | 1.7 | 2522 MB | 5 |

- **Table mode:** Docling 2.142.1 already defaults to `ACCURATE`, so the §6.1 baseline already used TableFormer V1's most accurate mode. `FAST` can only be worse and was not tried.
- **Cell matching:** turning it off gives 5/12 versus 4/12, with each file differing by at most one table in either direction (noise). **The default is unchanged.** The default log shows the `MatchingPostProcessor` warning "pdf cells ... dropped from the table" for nb-qt03, nb-qt04 and tb-qt05: PDF cells are dropped from tables, worth a separate investigation (text lost inside tables).
- **Thread count:** 4 → 12 cuts the time to 53%, with RAM and table quality unchanged. Variable `SOPILOT_PDF_THREADS` (default 4) and two new variables `SOPILOT_PDF_TABLE_MODE`, `SOPILOT_PDF_CELL_MATCHING` in `extract/pdf.py`. On the owner's machine set `SOPILOT_PDF_THREADS=12`.
- **Time target:** at 12 threads the most table-heavy document (`nb-qt01`) takes 5.0 s/page and the whole corpus averages 1.7 s/page, close to the 1.5 s/page target (≤ 30 s for 20 pages). ≤ 10 s/page is accepted for table-heavy documents.
- **TableFormer V2** (`docling-project/TableFormerV2`, Apache-2.0, 564 MB, run offline from the cache): tables matched 5/12 versus 4/12 for V1 at 12 threads (they differ on 3 files in both directions: nb-qt02 and nb-thanhtra06 gained, nb-qt04 lost), so no meaningful difference. It **returns no merged cells** (0 predicted; V1 predicted 24 and matched 2/8), peak RAM 2522 MB (V1 2159 MB), same time. Outside the labelled pages V2 produces a few very large tables (74 to 83 rows, 94–99% empty cells): these are blank forms (the "Sửa đổi tài liệu" (document revisions) table on page 2 of nb-qt03 really has about 38 empty rows; V2 produces 83), i.e. extra row splits rather than merged content; V1 produces no such tables. **No switch to V2.** It can be enabled with `SOPILOT_PDF_TABLE_MODEL=v2`; the default is `v1`.
- **Is text lost? (measured on whole documents, comparing words in the PDF text layer with the words Docling returns, list numbering included, 12 threads, one run):**

  | Family | V1 lost | V2 lost | V2 extra versus the PDF |
  |---|---|---|---|
  | `nb-*` (4 VI files) | 0.1–0.8% | 1.6–2.7% | 28–211 words |
  | `tb-*` (3 VI files) | 2.4–5.9% | 2.4–5.8% | 28–90 words |
  | `nb-thanhtra06` | 0.2% | 1.1% | 149 words |
  | `epa-*` (2 EN files) | 0.2–0.3% | 0.3% | 8–37 words |

  V1 loses almost no text in the body and tables: the cells "dropped" in the `MatchingPostProcessor` warning leave almost no trace (nb-qt03 lacks only "không nhận chấp"). V1's losses come from two other places: (1) **agency names in the logo cell of the page header** ("SỞ XÂY DỰNG", "CẢNG VỤ HÀNG HẢI THÁI BÌNH") are dropped on almost every page, so V2-21 cannot recover them from the output; (2) **process diagrams (flowcharts)**: `tb-qt03` page 5 loses about 128 of 154 words (83% of the page), because Docling treats the diagram as an image and does not take its text with OCR off. For SOPs this is a real loss (procedure steps live in the diagram). V2 loses more than V1 on every VI family with tables (column titles such as "tài liệu", "lần ban hành") and adds extra words. Limits of these figures: multiset word comparison (order ignored), one run, and glyph-error strings in the source PDFs (`aủ`, `nả`) also count as lost.
- **Recovering text in image regions from the PDF text layer (implemented in `extract/pdf.py`, 2026-10-26):** for every `picture` Docling returns, take the pdfium text inside its box (`get_text_bounded`), drop lines Docling already emitted on the same page (a multi-word line contained in emitted text; a one-word line only when it equals exactly one emitted element/cell), and require at least 2 remaining words. The result is a `paragraph` element with role `figure_text`, which the renderer puts into the Markdown (`NORMALIZER_VERSION` raised to `"2"`). Text in image regions lying entirely in the top 15% or bottom 10% of the page (logo cells) keeps role `header`/`footer` and does not enter the Markdown; V2-21 can still reclassify it. Lost words on whole documents: `tb-qt01` 60 → 30, `tb-qt03` 171 → 31, `tb-qt05` 46 → 1, `nb-qt03` 19 → 14; headings, tables and merged cells unchanged (4/12 tables, 22/33 headings, 2/8 merged cells), no slower. The `tb-qt03` page 5 diagram enters the Markdown with all 132 words. Remaining: "xây dựng" in `nb-*` (no image region), glyph-error strings, EPA footer codes, and a few logos on pages where Docling did not separate an image (5 occurrences of "cảng vụ hàng hải thái bình" remain in `tb-qt01`, `tb-qt03`). Limits: (1) text order is the PDF text-layer order; pdfium returns the `tb-qt03` diagram as **one continuous line**, so line-based dedup cannot split it further, and the page number inside the box (`5`) leaks into the start of the paragraph; (2) there are no arrows/edges, so the diagram is only a list of separate steps, and YES/NO branches are not attached to steps; (3) only 3 document families in the sample have images containing text.
- **Tables are still weak:** no configuration raised table matches above 5/12 (4–5/12 in every configuration; the sample is too small to tell them apart). `GraniteVisionTableStructureOptions` (VLM, heavy) has not been tried.

**Provisional thresholds** (labels not yet re-read by the owner, not used to close V2-20):

| Metric | Threshold | Current measurement |
|---|---|---|
| Heading text recall | ≥ 0.95 | 0.96–1.00 (met) |
| Heading precision, after boilerplate filtering in V2-21 | ≥ 0.85 | 0.64–0.88 raw (not measured after filtering) |
| Heading level, after inference from numbering in V2-22 | ≥ 0.90 | 0.65–0.69 (not met) |
| Tables detected correctly (recall) | ≥ 0.80 | 0.40 VI, 0.00 EN (not met) |
| Correct row and column counts, on detected tables | ≥ 0.70 | not measured separately |
| Merged cells | no threshold | not used |
| NFC; scans rejected with `NO_TEXT_LAYER` | 100% | met |

**Provisional decision:** heading levels inferred from numbering (V2-22); extra headings filtered in V2-21; `cell_spans = None` by default until merged cells are checked; nested tables are a known limitation, with `nb-qt01` page 4 kept as a regression test. Both table thresholds are unmet, so the final decision (accept, add a model, or handle hard tables separately) is the owner's after re-reading the labels.

## 7. Impact and consequences

- **Positive:** skipping the comparison spike let `V2-20` start directly on the adapter; MIT license; a single source of structure for PDFs.
- **Accepted trade-offs:** deciding before measurements; heavier dependencies (models, `torch`); if `V2-20`'s confirmation failed, switching the adapter would cost some work (small, since it is isolated behind `extract/pdf.py`).
- **Next actions:**
  - `V2-20`: confirm Docling per §5 and fill in §6.
  - `V2-19`: gather the minimum subset (≥ 6 Vietnamese PDFs, 2 EPA PDFs, 1 scanned PDF) for the confirmation run.
  - Update TECH-V2-ai-service §11 Q8, PRD-V2, PLAN-V2 (done together with this ADR).
