---
id: V2-22
title: "ai-service: document-type recognition, procedure tables and structure-aware chunking"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-07, V2-09, V2-28]
branch: "feat/ai-qa-structure-chunking"
assignee: pair
---

# TICKET V2-22: Structure-aware chunking

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
[AUDIT-ingestion-sop-data](../../../../research/audit-ingestion-sop-data-2026-10-19.md) steps 5, 6 and 7, PRD-V2 FR-08. The old standardizer recognized only Chương/Điều/Khoản (chapter/article/clause), lost titles, accumulated `section_path` wrongly, split sentences broken across lines, and the chunker counted tokens with `cl100k`.

## 2. Acceptance criteria
- [x] Recognize the document family (ISO procedure, Chương/Điều/Khoản, Markdown/wiki, non-standard prose) from V2-20's structure; Markdown headings (`#`) first, then numbering patterns (`1.`, `5.1`, `I.`, `Điều n`), heuristics (uppercase lines, bold) last. *Done 2026-10-26: `chunk/family.py`, `chunk/headings.py`.*
- [x] Section titles keep their full text (not just the number); `section_path` is the chain of ancestors, not sibling sections. *Done 2026-10-26.*
- [x] Procedure tables (Responsibility / Step / Description / Form): each row is a content unit with the column headers; long tables repeat the column headers when split. Changed 2026-10-21 (audit by query type, owner decision P0-3, TECH-V2-ai-service §5.2, §5.4): vertically merged cells (`DocElement.cell_spans`) are **repeated down each row** they cover when building the `content` of `PROCEDURE_STEP` chunks, so steps 3–4 under one merged "Trách nhiệm" (Responsibility) cell still have their owner; offsets and `row_spans` unchanged. Without `cell_spans`, no guessing. Test: a table fixture with merged cells (V2-19) gives the right `content` for each row. *Done 2026-10-26: `chunk/procedure_table.py`; tests that vertical merged cells are repeated down each row and nothing is guessed when `cell_spans = None`.*
- [x] Chunks carry the heading path (document title › section › step) in the embedded and BM25-indexed content. Changed 2026-10-21 (TECH-V2-ai-service §5.4): the chunker takes `title` and an optional `doc_code` as parameters; `index_text` = `"{title} [{doc_code}] › …"` with a code, `"{title} › …"` without; the issue number and effective date never enter `index_text`. Both forms tested. *Done 2026-10-26: `index_prefix`, both forms tested.*
- [x] Tokens counted with the embedding model's tokenizer through a `docproc.tokens.Tokenizer` passed to the chunker; implement `HFTokenizer` (loading `AutoTokenizer` for the active embedding's `model`/`revision`, without loading the embedding model) for `V2-09` and `eval/` to reuse (TECH-V2-ai-service §1.1). The chunker does not import `providers`. Chunks never exceed the model's limit; too-small sections are merged under the same parent; no splitting inside characters. *Done 2026-11-01: `docproc/tokens.py` has `Tokenizer`, `HFTokenizer` (parameter `local_files_only`); a separate extra `tokenizer = ["transformers>=4.40"]` in `pyproject.toml`. The test `test_real_embedding_tokenizer_keeps_chunks_within_limit` runs with the real `BAAI/bge-m3` tokenizer (revision `5617a9f6…`, local HF cache, offline, transformers 5.20.2): every `index_text` ≤ `max_tokens` and `token_count` matches the tokenizer's count; the test skips itself when the machine has no cache.*
- [x] Non-standard prose: split by paragraph/sentence, never hard-cut by token count. *Done 2026-10-26.*
- [x] Chunks work on the cleaned `StructuredDocument` and carry `char_start/char_end` on V2-20's canonical Markdown (owner decision 2026-10-21): an ordinary chunk is exactly the `markdown` substring at those offsets; a `PROCEDURE_STEP` chunk takes its offsets from the source row's `row_spans[i]` and its page from `row_pages[i]`; a table chunk split by rows takes its offsets from the first to the last row of its part; `page_start ≤ page_end` and they match the source elements' pages; a chunk covering a multi-page table has `page_end > page_start`. Checked with property tests on fixtures and the V2-19 corpus. *Partly done 2026-10-26: property tests on synthetic fixtures and real PDFs. Measured on the V2-19 corpus on 2026-11-03 (section below): 591 chunks / 21 files, 0 violations of any invariant; but the invariant "multi-page tables have `page_end > page_start`" could not be checked on the corpus because the extractor joined no table across pages (0 multi-page tables, the recorded V2-20 bug). Kept open pending the owner: accept checking multi-page tables only with fixtures, or wait for the table-joining fix and remeasure. Remeasured after the table-joining fix on 2026-11-04 (section "Joining multi-page tables and remeasuring 2026-11-04"): 7 multi-page tables, the `multi_page_table` invariant checks 3 chunks, 0 violations of any invariant on 564 chunks.*

## 3. Guide
- Replaces `services/ingestion-service/src/services/{standardizer,chunker}.py`; not a straight port.
- The chunk size matches the V2-07 eval configuration so the RQ results apply.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | The AUDIT §2.3 cases (title is only a number, accumulated path, "Điều 5" mid-sentence, `1. MỤC ĐÍCH`, `5.1`); procedure tables; Vietnamese characters at chunk edges | `uv run pytest tests/unit` |
| Eval | Headings and tables on the V2-19 corpus | per V2-19 |

### Implementation notes 2026-10-26
Code: `services/ai-service/src/sopilot_ai/docproc/chunk/` (`chunk_document(rendered, tokenizer, title=, doc_code=)`; 0 chunks → `EMPTY_CONTENT`). `ChunkConfig` defaults 384/512/64 per `models.yaml`. Docling's flat headings (level 1 for every heading) are rebuilt from the numbering when the document reports no hierarchy; a section `2. Procedure` that Docling returns as a list item is treated as a heading when there are no adjacent list items. A title prefix longer than half of `max_tokens` is shortened in `index_text` (ancestors dropped first), while `section_path` stays complete. Headings/tables not yet measured on the V2-19 corpus (see V2-19), not yet run with the real embedding tokenizer. Kept `review`.

### Measured on the V2-19 corpus 2026-11-03
Run (from the repo root, ai-service venv): `HF_HUB_OFFLINE=1 services/ai-service/.venv/Scripts/python.exe eval/check_chunks_corpus.py --structured eval/results/extraction-clean/structured --out eval/results/chunk-invariants/report.json`. Reuses the `StructuredDocument`s extracted in the V2-21 measurement round (`predict_extraction.py --clean`), without rerunning Docling. Process: `clean_document` → `render` → `chunk_document` with the real tokenizer `BAAI/bge-m3@5617a9f6…` (local HF cache), the default `ChunkConfig` 384/512/64, `title` = `doc_id`, `doc_code` = the extracted metadata. The invariants are implemented purely in `eval/sopilot_eval/chunk_invariants.py` (tests `eval/tests/test_chunk_invariants.py`), without adding heavy Docling tests to ai-service's `tests/unit`.

**Invariants** (full definitions in the docstring): `offsets` (0 ≤ start < end ≤ len); `substring` (`TEXT` = exactly the Markdown slice; `TABLE` = the slice, or a part split by rows: offsets from the start of its first row to the end of its last row of one table, content = repeated column headers + exactly that slice, or a piece of an overlong row); `procedure_row` (`PROCEDURE_STEP` has offsets = `row_spans[i]` and `page_start = page_end = row_pages[i]`); `page_order`; `page_source` (a chunk's pages = the min/max pages of the table rows or source elements it covers); `multi_page_table` (a chunk covering table rows on several pages has `page_end > page_start`); `token_budget` (≤ 512).

| | Result |
|---|---|
| Files / chunks | 21 files (19 PDF, 2 MD) / 591 chunks: 543 `TEXT`, 42 `PROCEDURE_STEP`, 6 `TABLE` |
| Checks | offsets 591, substring 549, procedure_row 42, page_order 591, page_source 549, token_budget 591, multi_page_table **0** |
| Violations | **0** for every invariant (no violating examples); no file `EMPTY_CONTENT` |
| Rendered tables | 122, of which **0** multi-page (`row_pages` over > 1 page) |

**Bug revealed (V2-20, reported only):** the gold labels have 34 table pieces `page_fragment` (tables spanning pages), but `extract/pdf.py` `_merge_tables` joined no pair. Of 64 "table at the end of page p / table at the start of page p+1" pairs (`table_continuation_blockers` in the report): 24 because page p ends with a non-table element, 19 because of different column counts, 15 because there is a content element before the table on page p+1, 6 because the header row is not repeated, 0 eligible. The main cause in Vietnamese ISO: the page header is a **content table** at the top of each page (for example `nb-qt01` pp. 5→6: a 5-column procedure table spans the page, and page 6 opens with the 4-column header table "SỞ | QUY TRÌNH | Mã hiệu: | QT-01"), while joining runs at extraction time, before cleaning; also, continuation pieces often do not repeat the header row (label convention 3). Proposal: join tables after the boilerplate step (skipping `header/footer/boilerplate` elements between two pieces) and allow joining with the same column count even without a repeated header; then remeasure the `multi_page_table` invariant on the corpus.

**Limits:** the invariants are necessary conditions on offsets/pages, not a measure of chunk boundary quality; `page_source` compares with the pages the extractor assigned, not the gold labels; the corpus has only 6 `TABLE` and 42 `PROCEDURE_STEP` chunks; the labels were reviewed by an agent by delegation. Thresholds (if any) pending the owner.

### Joining multi-page tables and remeasuring 2026-11-04
Fixed the table-joining bug of the section above. `extract/pdf.py` `_merge_tables` keeps its conditions (the next table right after, the same column count, a repeated header row) and only calls a shared function in the new `docproc/tables.py`; so the old `structured/*.json` stay valid and Docling was not rerun. A new step, `join_continued_tables`, runs inside `clean_document` **after** `mark_repeated_header_footer` (table-shaped headers are already boilerplate) and before `mark_frame_blocks`: two body tables are joined when only `header/footer/boilerplate`/`page_break` elements lie between them, the second is on page `page_end + 1`, with the same column count, and either repeats the header row (the repeated row is dropped) or has no header row (`header_rows = 0`, a continuation without a repeated header); a next-page table with a different header is a new table. `row_pages`, `cell_spans`, `page_end` are updated as in the extractor. The chunk/`PROCEDURE_STEP` logic is unchanged. Tests: `test_table_split_by_a_header_table_is_joined_after_cleaning_and_chunks_span_pages` (a 4-page procedure table split by header tables, each `PROCEDURE_STEP` on its row's page; a 2-page ordinary table has a chunk with `page_end > page_start`) and `test_next_page_table_with_its_own_header_is_not_joined` in `tests/unit/test_clean_corpus_fixes.py`.

Run as in the section above (real `BAAI/bge-m3` tokenizer, `eval/results/chunk-invariants/report.json` overwritten), after the same day's V2-21 fixes:

| | Before (2026-11-03) | After (2026-11-04) |
|---|---|---|
| Chunks | 591 (543 `TEXT`, 42 `PROCEDURE_STEP`, 6 `TABLE`) | 564 (500 `TEXT`, 54 `PROCEDURE_STEP`, 10 `TABLE`) |
| Rendered tables / multi-page | 122 / **0** | 88 / **7** (`nb-qt01` 1, `nb-qt03` 2, `nb-qt04` 1, `tb-qt05` 3); 11 joins |
| `multi_page_table` checks | 0 | **3** |
| Other checks | offsets 591, substring 549, procedure_row 42, page_order 591, page_source 549, token_budget 591 | offsets 564, substring 510, procedure_row 54, page_order 564, page_source 510, token_budget 564 |
| Violations | 0 | **0** for every invariant |

Tables decreased because ISO header tables are now boilerplate; `TEXT` chunks decreased because repeated headers no longer enter the body. "Table at the end of page p / table at the start of page p+1" pairs remaining **after** cleaning: 32 (14 with a body element before the next page's table, 9 with a body element after the previous page's table, 9 with different column counts; 0 because of an unrepeated header). Most are genuinely different tables (a form list after the procedure table, appendix forms); the rest come from page headers not recognized as boilerplate (`nb-qt01` pp. 4→5, `tb-qt05` pp. 4→5, `nb-thanhtra06` pp. 3→4) or Docling inferring different column counts for the two pieces (`nb-thanhtra06` 4 ↔ 5 columns): not fixed; needs column alignment by position instead of column count. The report's `table_continuation_blockers` field is still computed on elements **before** cleaning (the extractor's conditions, 64 pairs, unchanged). The gold has 34 `page_fragment` pieces; the individual joins have not been scored against the labels. Thresholds (if any) pending the owner.

### Owner sets thresholds and closes the ticket 2026-11-04
(This section repeats the text of V2-21's closing section, as in the original.)
The owner accepted the recommendation: `header_footer_ratio` = 0.4 (TECH §5.3 edited the same day). V2-21 acceptance thresholds: **leakage ≤ 10%** and **wrongful removal ≤ 2%** on the V2-19 corpus. Post-fix measurements: leakage **8.1%** (met), wrongful removal **1.6%** (met; all label disagreements over revision-history tables, 0 real errors). Known limitation: Vietnamese leakage **13.8%** (above 10%), because Docling cuts headers differently across pages; tracked in V2-07. A sample check of the 176 removed blocks the labels do not confirm: running headers, page numbers, footers, "Nơi nhận" lists, signatures, document numbers, revision-history tables; the random sample showed no real content. The 10%/2% thresholds were proposed by the assistant, not derived from their effect on retrieval. Evidence: `validate-build.ps1 -Scope ai` green, 104 ai-service tests and 70 eval tests pass (2026-11-04). Closed `done`.
