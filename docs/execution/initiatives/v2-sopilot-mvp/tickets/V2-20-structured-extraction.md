---
id: V2-20
title: "ai-service: Docling (ADR-008), structured representation and canonical Markdown with offsets (PDF/MD)"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-19]
blocks: [V2-09, V2-21, V2-22]
branch: "feat/ai-structured-extraction"
assignee: pair
---

# TICKET V2-20: Structured extraction

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
[AUDIT-ingestion-sop-data](../../../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) steps 2 and 3, PRD-V2 FR-08. The old code had 3 extractors and lost page numbers, heading structure, numbering and table positions. Replace them with a single module producing a typed document tree (headings, paragraphs, lists, tables) with page numbers and character positions.

Owner decision 2026-10-21 ([AUDIT-markdown-normalization](../../../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md), TECH-V2-ai-service §5.2, §11 Q7–Q8): PDFs are converted directly from **Docling**'s structure (ADR-008, decided the same day) into `StructuredDocument`; Markdown goes through a parser into the same representation; ai-service renders the **canonical Markdown** after cleaning and records offsets on it. No plain-text extraction followed by rebuilding, no fallback chain, no OCR, no LLM rewriting. TXT is dropped from the MVP.

## 2. Acceptance criteria
- [x] Scaffold `services/ai-service` (TECH-V2-ai-service §1.1, "Scaffolding order"): `pyproject.toml` (uv, Python ≥ 3.11, a `pdf` extra for Docling, version pinned per ADR-008), the `src/sopilot_ai/` layout with a pure `docproc/` (no DB/web imports), `tests/unit`, ruff. Add the `ai` scope to `scripts/validate-build.ps1` and `scripts/check-conventions.ps1`, the `ai-service` scope to `scripts/run-tests.ps1`, and update the scope table in `AGENTS.md` in the same change. *Done 2026-10-26: `pyproject.toml`, `src/sopilot_ai/docproc`, `tests/unit`, the `ai`/`ai-service` scopes in the scripts and AGENTS.md.*
- [x] Changed 2026-10-21 (owner decision [ADR-008](../../../../architecture/decisions/adr-008-pdf-extraction-docling.md): **Docling**, `approved`, no measurements): this ticket **confirms Docling** and no longer compares two libraries. On the V2-19 subset (or labelled synthetic fixtures, per AUDIT-markdown-normalization §6.3), check ADR-008 §5's hard constraints: (1) offline on CPU, models loaded from `SOPILOT_PDF_ARTIFACTS_PATH`; (2) OCR fully off (image pages yield 0 characters); (3) real page numbers for every element, and `furniture` or enough page information for `V2-21`; (4) Vietnamese NFC without lost diacritics; (5) the MIT license. Also measure: whether the library returns **merged-cell spans** (`cell_spans`: row, column, rowspan, colspan) on V2-19's tables with merged cells; time and peak RAM per page on the owner's machine; headings/tables per document family. Record real measurements, the pinned Docling version and any limitations in ADR-008's §6 table; anything unmeasured is recorded as unmeasured. Timebox at most 2 days (the PLAN's old ceiling); if done early, move on to the adapter. *Partly done 2026-10-26: measurements in ADR-008 §6. Offline operation with pre-downloaded models not yet proven; time exceeds the starting target on table-heavy documents (reported to the owner).*
- [x] Changed 2026-10-21: **if a hard Docling constraint fails, stop and ask the owner**: ADR-008 goes back to `draft`; do not switch to PyMuPDF on your own or add a fallback chain (AGPL needs owner confirmation, PLAN-V2 §4). Missing `cell_spans` or time/RAM over the starting target do not by themselves send the ADR back to `draft`: record them in ADR-008 §5–§6 and tell the owner. The runtime depends only on Docling, isolated in `extract/pdf.py`.
- [x] Accept only PDF/MD; reject DOCX/TXT before parsing (`UNSUPPORTED_TYPE`). No DOCX/TXT extractor or conversion is implemented.
- [x] PDFs with a text layer: page numbers kept; reading order correct for multi-column pages; tables keep their row/column structure in the right place in the body; merged cells not duplicated in the canonical Markdown. Changed 2026-10-21: the adapter fills `DocElement.cell_spans` (TECH-V2-ai-service §5.2) for every merged cell so `V2-22` can repeat values down each row; when the library returns no spans, `cell_spans = None` and the limitation is recorded in ADR-008, without guessing values. Test: a 4-column table fixture with a "Trách nhiệm" (Responsibility) cell merged vertically over 2 rows gives the right `cell_spans`. A table spanning several pages is one element with `page_end > page` and `row_pages` per row (TECH-V2-ai-service §5.2).
- [x] MD: a CommonMark + GFM parser; headings, lists and tables kept; frontmatter removed (stored as metadata) and Hugo shortcodes removed; embedded HTML kept as text; non-UTF-8 → `INVALID_ENCODING`.
- [x] PDFs without a text layer → `FAILED NO_TEXT_LAYER` with a fixed VI/EN sentence; encrypted PDFs → `ENCRYPTED_PDF`; corrupt files → `CORRUPT_FILE`. OCR off: a test that an image-only page yields 0 characters and no OCR engine is called.
- [x] The canonical Markdown renderer (TECH-V2-ai-service §5.2) has a `normalizer_version`: headings `#` by level, lists keeping the source numbering, GFM tables with exactly the source element's rows/columns, merged cells written once. Rendering the same input twice gives the same string. The renderer sets `row_spans` for every row of every table.
- [x] Source mapping: for every content element of every fixture and every existing corpus file, `markdown[char_start:char_end]` equals the element's rendered text (an invariant, checked with property tests); `page` within `1..page_count` for PDFs, `None` for MD; `page_index` consecutive and non-overlapping, multi-page tables split at row boundaries; `row_spans` increasing, inside the table's offsets, each span containing exactly the cells of its row; UTF-16 offsets correct for strings with emoji/non-BMP characters.
- [x] Unicode: NFC output; Vietnamese fixtures (every tone mark, `đ`, uppercase letters with diacritics) and English ones give exactly the expected strings in both PDF and MD; a fixture with broken characters produces the `UNMAPPED_GLYPHS` warning (V2-21).
- [x] Self-made heading/table fixtures (PDFs exported from Vietnamese Word: 2-level numbered headings, `a)` lists, a 4-column table with merged cells and a table spanning 2 pages): headings in the right order and level, tables in the right place in the body with the right rows/columns. No exact-match requirement on the real corpus.
- [x] Report metrics on the V2-19 corpus by document family (heading precision/recall, tables, time/RAM per page); the owner sets thresholds after seeing the baseline, none set in advance. *Done 2026-10-26 (ADR-008 §6.1): heading text recall 0.96–1.00 but flat heading levels; table recall 0.40 VI and 0.00 EN; merged cells 0/2 VI. Scored on selected-page labels reviewed by Claude on the owner's behalf; not yet re-read by the owner, no thresholds set yet.*

## 3. Guide
- **Files:** a pure Python package, without DB/web dependencies, in `services/ai-service` per the TECH-V2 structure (V2-03). V2-09 imports it.
- Old bugs for reference: `services/ingestion-service/src/services/extractors/`, `preview_extractor.py`.

## 3a. Measurement tools (2026-10-26)
- `eval/predict_extraction.py` runs `docproc` on the labelled corpus and writes predictions; `python -m sopilot_eval.extraction --selected-pages` scores on the selected pages (a new mode; the `evaluate` mode still refuses partial labels). The adapter adds `DocElement.header_rows` (the number of column-header rows Docling marks).

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | Multi-page PDFs, tables in the body, merged cells, multi-page tables (`page_end`, `row_pages`, `row_spans`); MD (frontmatter, GFM, embedded HTML); the renderer and offset invariants; VI/EN Unicode; rejecting DOCX/TXT, scanned, encrypted and corrupt PDFs | `uv run pytest tests/unit` |
| Confirmation | Docling on the V2-19 subset, owner's machine: hard constraints, `cell_spans`, time/RAM; results in ADR-008's §6 table | script in `eval/` |
| Eval | The V2-19 scoring script on the whole corpus, results stored in the report | per V2-19 |

### Closing the ticket 2026-11-03
The owner set `done`. Evidence: every criterion ticked; `validate-build.ps1 -Scope ai` green (compileall + ruff), `run-tests.ps1 -Scope ai-service -Type unit`: 96 tests pass (2026-11-03).
