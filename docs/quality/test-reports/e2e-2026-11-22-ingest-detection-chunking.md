---
id: TEST-REPORT-005
title: "Document type detection, chunking strategy and chunk results on the pilot corpus, 2026-11-22"
status: draft
created: 2026-11-22
updated: 2026-11-22
author: "Owner"
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-46-processing-report-chunks-view.md
  - docs/architecture/components/ai-service.md
---

# TEST-REPORT-005: Detection and chunking over the pilot corpus

## 1. Verdict

Detection and strategy are right for all 21 files that have text and the 4 scans fail as designed (F1 was found and fixed the same day, see section 4); no chunk is over the size limit and no text was found lost. One real weakness remains open: step tables that continue on another page lose their column names (F2). There is no gold chunking, so "right" here means invariants plus spot checks, not a score.

- Commit `6f8bf49` plus uncommitted changes. The real pipeline (`process_document`: Docling, clean, family, chunker, bge-m3 tokenizer, `models.yaml` chunk sizes) was run offline over the 25 files of `datasets/extraction/pilot` (manifest family as the independent label). The script is not committed (it lives in the session scratchpad); it only reads the pipeline.
- Not run through the UI or the database; the same code runs in the worker.

## 2. Detection and strategy

| Source family (manifest) | Files | Detected | Verdict |
|---|---|---|---|
| `iso_9001` (VI SOPs) | 8 | `ISO_PROCEDURE` x8 | correct |
| `epa_sop`, `fda_sop`, `gmp_sop` (EN SOPs) | 6 | `ISO_PROCEDURE` x6 | correct (section words; no step table in most) |
| `wiki_markdown` | 2 | `MARKDOWN` x2 | correct |
| `administrative`, consolidated decree with 21 articles (`vn-vbhn109`) | 1 | `LEGAL_ARTICLES` | correct, 21 of 21 articles have their own chunk |
| `administrative`, short decision with 3 articles (`vn-qd1308`) | 1 | `MARKDOWN`, after the F1 fix `LEGAL_ARTICLES` | **miss, fixed** (F1) |
| `non_standard` (`vn-qd82`, `vn-tb425`, `vn-cv10065`) | 3 | `LEGAL_ARTICLES` (was `MARKDOWN`, F1), `MARKDOWN`, `PROSE` | correct after the F1 fix |
| Scans (`nd30`, `vn-nq311/424/432-scan`) | 4 | `FAILED NO_TEXT_LAYER` | correct, as designed |

The strategy follows the family in every case (the rules shown by the report are the ones `Chunker` applies).

## 3. Chunk results (21 files that produced chunks, about 640 chunks)

| Check | Result |
|---|---|
| Chunks over 512 tokens | 0 |
| `SECTION`/`PROSE` chunk text equals the Markdown slice of its range | all; the only inequalities are step and table chunks (count matches exactly in every file), as designed |
| A chunk spanning two article headings (`LEGAL_ARTICLES`) | 0 |
| Every article heading has its own chunk (`vn-vbhn109`) | 21 of 21 |
| Text present in the Markdown but outside every chunk range | looked at 7 files with the largest gaps: table of contents lines (`epa-soil`, not indexed), numbered lines the outline treats as headings (their text is in the section path), and continuation rows of a step table (merged into the step chunk). The suspected losses (`vn-qd82` article 2, `tb-qt05` continuation rows, a `vn-vbhn109` sentence) were found inside chunks. No real loss found. Not all 21 files were read by hand |
| Chunks under 64 tokens (excluding steps) | about 35, mostly document header fragments (`Số:`, `VĂN BẢN HỢP NHẤT`) and short sibling sections that cannot merge |

## 4. Findings

### F1. A short decision whose articles are not headings is not recognized as legal (medium, fixed)

`vn-qd1308` has `Điều 1`, `Điều 2`, `Điều 3`, but Docling returns them as a paragraph, a heading and a list item (`- Điều 3. ...`), so only 1 article heading is seen and the file becomes `MARKDOWN` (needs 3 headings). `vn-qd82` is the same. Effect: chunks follow the heading tree, not one chunk per article. **Fix (2026-11-22, uncommitted):** body lines that open with `Điều N` / `Article N` (paragraph or list item, any length) now count as article evidence next to article headings, same threshold of 3 (`is_article_line` in `headings.py`, `family_of` and `family_evidence` in `family.py`); the outline is unchanged, so no article text moves into a heading. Three new unit tests (a decision with article as paragraph, heading and list item is `LEGAL_ARTICLES`; two lines are not enough; the evidence counts headings and lines apart). Corpus re-run: only `vn-qd1308` and `vn-qd82` changed family; every other file has the same family and chunk count. Side effect: the legal strategy does not merge short sections, so `vn-qd1308` goes from 43 to 44 chunks and `vn-qd82` from 3 to 5 (one more chunk under 64 tokens each). The chunks are still not one per article for these decisions, because their articles are body text. Suites: ai-service 864 passed (unit and integration), web 230 Vitest, ruff clean.

### F2. A step table continued on another page loses its column names (medium)

`tb-qt05` steps 5 and 6 are labelled `Cột 1`, `Cột 2`, `Cột 3` instead of `TT`, `Hoạt động`, `Trách nhiệm`, because the header row appears only on the first page. The text is still indexed, but the chunk reads worse and keyword match on the column name is lost.

### F3. A long step becomes several chunks and later parts lose the step number (low)

`nb-qt03` has 6 numbered steps and 12 step chunks; the second chunk of a step starts with the text and not with `TT: n`. Retrieval still finds it through the section path, but the step number is not in the embedded text of the continuation.

### F4. The first lines of a document become tiny chunks (low)

`vn-vbhn109` has chunks `Số:` (9 tokens) and `VĂN BẢN HỢP NHẤT` (25 tokens). Harmless for answers, noise in the chunk list the processing report shows.

### F5. Table of contents is not indexed in some files (info)

`epa-soil` table of contents lines are in the Markdown but in no chunk. Probably intended; not confirmed in the design.

## 5. Not checked

- Whether the chunk boundaries are what a person would draw (no gold chunking). The V2-19 labels cover only some pages.
- Retrieval quality after chunking (that is RQ1 to RQ3).
- The 4 scans beyond the failure code; PDFs outside this corpus; Markdown with a step table (none in the corpus).
- Full manual reading of every chunk.

## 6. Proposed scenarios

- A unit test that a step table continued on a second page keeps its column names (F2).

## 7. Addendum: root causes from the raw Docling output (2026-11-22)

`extract()` was run on `vn-qd1308`, `vn-vbhn109` and `tb-qt05` and compared with the PDF text layer (pypdfium2). Docling returns the text faithfully; the faults below are in our cleaning and chunking unless marked Docling. Checked on three files only, not against page images.

| Symptom | Raw Docling output | Fault |
|---|---|---|
| "2. Nghị định này bãi bỏ toàn bộ các Nghị định:" and "1 Nghị định số 366/… như sau:" are section titles | `paragraph` | ours: `headings.py` promotes numbered lines |
| Table of contents chunked as content (`tb-qt05` chunk #1) | `list_item` "1. MỤC ĐÍCH"… | ours: chunker |
| Lines of underscores and "Hà Nội, ngày…" as tiny chunks | present in the PDF text layer | ours: no decorative-line rule; `LEGAL_ARTICLES` never merges |
| Letterhead "CẢNG VỤ THÁI \| QUY TRÌNH… \| Mã hiệu: \| QT.05" chunked as content and as fake steps | a 3x4 `table` on pages 5, 7, 8, 9 | ours: repeated-table detection misses it |
| Step rows cut at a page break, steps labelled `Cột N` | one table per page, `header_rows=0`, first row with empty cells holding the overflow text | ours: continuation row not stitched; cause of `Cột N` not proven |
| "Số:" and "/2026/VBHN-NĐ-NHNN" split | the PDF has "Số: /2026/VBHN-NĐ-NHNN" on one line | Docling reading order |
| Articles 1, 2, 3 of `vn-qd1308` as paragraph, heading, list item | inconsistent classes | Docling (compensated by F1) |
| Footnote "1 Nghị định số 366…" at the top of page 1 | reading order | Docling, harmless |

Fixes are planned in [V2-47](../../execution/initiatives/v2-sopilot-mvp/tickets/V2-47-ai-service-chunk-quality-fixes.md). Also found by that ticket's review: finding F5 says a table of contents is not indexed (`epa-soil`) while `tb-qt05` chunk #1 is one; both can be true (the table of contents rule depends on the heading).

## 8. Result after V2-47 (2026-11-22)

Re-run on the same 25 files with `eval/check_chunks_pilot.py` (per-file tables and definitions in V2-47 section 7). Families unchanged, the 4 scans still `NO_TEXT_LAYER`, 0 chunk invariant violations.

- **F2 fixed.** The `tb-qt05` letterhead table (identical on pages 5, 7, 8, 9, below the 40% repeat share) is now header, so the step table parts are joined; the overflow rows at page breaks are stitched into the step they continue; the page-7 part that Docling cut one column narrower, with the overflow row as a header, is joined too. Result: 8 whole steps (before: 6, two of them labelled `Cột 1/2/3`), every one labelled `TT | Hoạt động | Trách nhiệm | Yêu cầu | Biểu mẫu`. The cause of `Cột N` was that page-7 part being a table of its own.
- **F4 fixed for the legal family.** `vn-vbhn109` "Số:" and "/2026/VBHN-NĐ-NHNN" are merged into the preamble chunk; lines of underscores are removed as decorative lines in every family; three numbered lead-in sentences ending in ":" are no longer section titles. Left: "Hà Nội, ngày tháng năm 2026" after the last article (28 tokens).
- **F5 explained and fixed.** A table of contents under a `Mục lục` / `Contents` heading is no longer chunked (`tb-qt01`, `tb-qt03`, `tb-qt05`, `nb-thanhtra06`, `epa-qc`). Left: in `epa-qc` the entries from "4. Internal Quality Control Procedures" on are read as a heading, so that tail is still one small chunk.
- **F3 not fixed** (out of scope): a split step still loses its number in the continuation chunk.
- Boilerplate on the V2-19 corpus: leakage 8.1% → 6.2%, wrongful removal 1.6% unchanged (11/706).
- The RQ numbers of V2-07 and the sets of V2-37 and V2-45 were measured with the chunker and Markdown before V2-47; they are not comparable with chunks built after it (owner decision 2026-11-22: the submitted results stay as they are, no re-freeze).
