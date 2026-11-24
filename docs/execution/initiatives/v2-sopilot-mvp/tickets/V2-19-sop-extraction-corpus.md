---
id: V2-19
title: "Real SOP corpus (VI, EN; PDF/MD) and extraction-quality measurement"
type: test
status: done
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-20, V2-28]
branch: "test/tests-extraction-corpus"
assignee: pair
---

# TICKET V2-19: SOP extraction corpus and measurement

> Translated from Vietnamese on 2026-11-13; content unchanged. Unchecked criteria were left unchecked in the original when the owner closed the ticket on 2026-11-03 (see "Owner closes the ticket").

## 1. Context & goal
[AUDIT-ingestion-sop-data](../../../../research/audit-ingestion-sop-data-2026-10-19.md) step 1. V2-06's eval corpus has only English Markdown, so it cannot measure extraction of Vietnamese PDFs with a text layer. A small set of real documents with structure labels is needed as the yardstick for V2-20 to V2-22.

This set measures **extraction and structure**, not retrieval; it is not mixed into RQ1–RQ5.

Changed 2026-10-21 ([AUDIT-markdown-normalization](../../../../research/audit-markdown-normalization-and-preview-2026-10-21.md)): TXT is dropped from the MVP, so it is not part of the quality corpus; a **minimum subset** must be ready first, because `V2-20`'s Docling confirmation (ADR-008, 2-day timebox) uses it.

## 2. Acceptance criteria
- [ ] 20–50 files covering at least 5 families: ISO 9001 procedures, administrative documents (Decree 30/2020, Chương/Điều/Khoản (chapter/article/clause)), GMP/EPA SOPs, wiki/Markdown, non-standard documents. PDFs with a text layer and MD; plus 2–3 scanned PDFs to test rejection and at least 1 PDF with a text layer but some image-only pages (the `PAGES_WITHOUT_TEXT` warning). DOCX (deferred) and TXT (dropped 2026-10-21) are not in the quality corpus; only upload-rejection fixtures are needed in V2-12. The TXT sources in RESEARCH-V2-19 (for example curl RELEASE-NOTES) need not be collected.
- [ ] A minimum subset for `V2-20`'s Docling confirmation, with owner-approved heading/table labels: ≥ 6 Vietnamese PDFs (preferably the 4 group-A ISO PDFs of RESEARCH-V2-19 with procedure tables), 2 English PDFs (EPA), 1 scanned PDF. If not ready, V2-20 uses synthetic fixtures per the rules of AUDIT-markdown-normalization §6.3.
- [ ] Every file records its source, license and family label in `datasets/extraction/SOURCES.md`. Files that cannot be redistributed: commit a manifest + download script, not the file. Internal documents must have sensitive information removed before inclusion.
- [ ] Gold labels per file: the ordered list of headings (with levels), the tables (position, column headers), the boilerplate blocks to remove (headers/footers, national motto, signatures, approval tables, revision tables), the expected metadata (document code, issue number, effective date) where present.
- [ ] A scoring script for any extractor: heading match (precision/recall by order and level), tables in the right position with the right rows/columns, the boilerplate leakage rate, metadata correctness, broken characters (`U+FFFD`, `(cid:`), processing time and peak RAM per page. Reported by document family and language, not only a corpus-wide average.
- [ ] Changed 2026-10-21 (end-to-end audit by query type, owner decisions D6/P0-3/P0-4): gold labels also include (a) tables with **merged cells** (cell position, rowspan/colspan) to score `V2-20`'s `cell_spans` and `V2-22`'s `PROCEDURE_STEP` chunks; (b) at least 2 **1–2-page** PDFs (checking that the header/footer rule does not delete the title and last paragraph); (c) the positions of cross-references within a document ("theo mục 5.3" (see section 5.3), "Điều 12" (Article 12)) and across documents ("theo QT-05" (per QT-05)).
- [ ] Changed 2026-10-21 (D6): a script counting cross-reference frequency (within and across documents) over the whole corpus, with the numbers in `V2-19`'s report. This is the basis for revisiting TECH-V2-ai-service §6.4a's "Not done"; no threshold is decided before the numbers exist.
- [ ] The owner reviews each file's labels.

## 3. Guide
- **Files:** `datasets/extraction/` (CREATE), the scoring script in `eval/` next to the V2-05 harness.
- The owner provides or chooses documents; the agent prepares the label format and scripts.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | The scoring script on 2 hand-labelled sample files | `uv run pytest` in `eval/` |

### Preparation 2026-10-24 (data not yet accepted)
There are a draft manifest/labels and two synthetic MD fixtures in `datasets/extraction/example/`; the validator/scorer `eval/sopilot_eval/extraction.py`, the contract in `datasets/extraction/README.md`. It scores headings with order/level/page, tables, merged cells, boilerplate, metadata, broken characters and reference counts, reported by family/language. The predictions are hand-written examples; time/RAM not measured. There are not yet 20–50 real documents, a PDF subset for Docling or owner-approved labels; the corpus criteria are still not met.

### Acquisition pilot 2026-10-25 (corpus not yet accepted)
Downloaded and SHA-256-locked **11 real PDFs / 224 pages** in `datasets/extraction/pilot/`: 8 Vietnamese SOPs with a text layer, 2 English EPA SOPs, 1 Vietnamese PDF without text per pypdf. Four Ninh Bình SOPs have a textless first page (`mixed`); Decree 30 has 76/76 pages without extractable text, and the page 1 image confirms a scanned page. No OCR. There are enough candidate files for the 6 VI + 2 EN + 1 scan subset, but **not yet the owner-approved label gate** for acceptance.

The draft heading/table/merged-cell/boilerplate/metadata/reference labels cover only **the selected pages**, not whole documents. QT-01 page 4 has a nested table/horizontal merged cells; the representation of tables and of the parts spanning pages needs review. The scorer refuses whole-document scoring with partial labels and refuses to fold rejection fixtures into heading/table scores. Docling not yet run, latency/RAM not measured. Not yet 20–50 files/5 families, short PDFs or the required number of scans; no corpus criterion is marked done.

PDFs/images are local only (gitignored), with sources/rights pending per-file verification; a manifest + download script are committed instead of binaries. See [SOURCES](../../../../../datasets/extraction/SOURCES.md), [README](../../../../../datasets/extraction/pilot/README.md), the [review sheet](../../../../../datasets/extraction/pilot/REVIEW.md) and the [pilot HANDOFF](../../../../research/research-v2-06-v2-19-pilot-review-2026-10-25.md). Kept `in-progress`; the owner has not reviewed any file/label yet.

### Corpus expansion 2026-10-26 (not yet accepted)
The owner delegated label review to Claude and set `review_status=reviewed` for the files in V2-19's scope (`reviewer_id=claude-delegated:tiên`; the owner has not re-read this round's labels). The corpus now has **23 files** (21 PDFs, 2 Markdown) in 6 family groups (iso_9001, epa_sop, fda_sop, administrative, non_standard, wiki_markdown); 4 scanned PDFs (nd30 + 3 Standing Committee resolutions of 1–3 pages), 2 short PDFs with text (2 pages), 4 ISO PDFs with a textless first page. Licenses: EPA/FDA/k8s verified by policy/LICENSE; Vietnamese documents verified secondarily (Article 15 of the IP Law, the law itself not read); the 8 Vietnamese ISO PDFs are still unverified. Round 3 (2026-10-26): every page image of all 23 files viewed and `annotation_scope=full_document` set; `--require-reviewed` green (a form check only; the labels have not been re-read by the owner). Still missing: a real GMP SOP (only the FDA ORA-LAB template), the licenses of the 8 Vietnamese ISO PDFs, a corpus cross-reference counting script, the owner's review. Kept `in-progress`. Details: [SOURCES](../../../../../datasets/extraction/SOURCES.md), [pilot README](../../../../../datasets/extraction/pilot/README.md).

### Owner reviews the labels 2026-11-01 (ticket not yet accepted)
The owner personally viewed every page of all **23/23 files** with the local app `eval/review_ui/server.py` (the page image next to its labels, with the agent's notes flagging "NOT SURE" spots) and confirmed: all 1365 labels kept (0 removed, 0 edited, 0 added), metadata unchanged. Each record now has `reviewer_id=owner:tiên`, `owner_confirmed=full_document`, `owner_review_changes`; the earlier delegated reviewer is kept in `delegated_reviewer_id`. `sopilot_eval.extraction --require-reviewed` is **green**. The criterion "The owner reviews each file's labels" is met for the 23 existing files. Still missing: a real GMP SOP, the licenses of the 8 Vietnamese ISO PDFs, the corpus cross-reference counting script. Kept `in-progress`. The data files are in `datasets/` (gitignored), with a pre-review backup in `datasets/extraction/pilot/local/backups/`.

### Completing the corpus 2026-11-01 (pending owner review of 2 new files)
- **Real GMP SOPs:** added 2 English `gmp_sop` PDFs from Frederick National Laboratory (NCI), Biopharmaceutical Development Program: SOP 21301 *Deviations* (17 pages) and SOP 12188 *Labeling and Storage of CGMP Raw Materials, Samples, and Equipment* (5 pages). Text layer present, SHA-256 locked, preview images; labels are **drafts by Claude** (`review_status=draft`), to be reviewed by the owner in `eval/review_ui/server.py`. The source page allows downloading for use by cGMP facilities but says nothing about redistribution, and the operator is a contractor, so the binaries stay local. Corpus: **25 files** (23 PDFs, 2 Markdown), 7 family groups, `corpus_version=sop-pdf-pilot-2026-11-01-v3`.
- **Licenses of the 8 Vietnamese ISO PDFs:** verified **secondarily** under Article 15(2) of the IP Law and Decree 17/2023/NĐ-CP Article 8 (documents of state agencies are not protected by copyright), at the same level as the other Vietnamese documents; the Official Gazette was not read. Details and debatable points in [SOURCES](../../../../../datasets/extraction/SOURCES.md).
- **Corpus cross-reference count:** `eval/sopilot_eval/crossref.py` (8 unit tests), results in `eval/results/crossref-v2-19.json`. Regex candidates on the text layer, excluding labelled furniture; a document mentioning its own code and forms of the same procedure count as within-document; internal codes (QT-02) match only documents of the same agency. On the 21 files with text: **16/21 files have within-document references** (189 occurrences, mostly BM-xx forms, "mục/Điều/Section"), 218 references to other documents but **only 3 (1.4%) point to documents in the corpus, in 2/21 files** (nb-qt01 → nd30; nb-qt04 → nb-qt02, nb-qt03). Density 5.6 references/1000 words (VI 6.8; EN 4.2). The regex count is higher than the gold labels because the labels do not record every repetition; these are candidates, not adjudicated labels. Basis for TECH-V2-ai-service §6.4a: expanding references **across documents** has almost no targets in the sample workspace; references **within a document** are more common. The decision threshold is left to the owner.
- Remaining: the owner reviews the labels of the 2 GMP SOPs so the gate turns green again. Kept `in-progress` until then.

### Review of the 2 GMP SOPs and completing the gate 2026-11-03 (pending owner acceptance)
An Opus 5.5 agent viewed every page image of `nci-bdp-labeling` (5/5) and `nci-bdp-deviations` (17/17): 0 wrong/missing labels; only the `coverage_note`/`review_notes` of deviations were edited. The records state `reviewer_id=owner:tiên` at the owner's direction, `owner_confirmed=delegated_opus_full_document` (unlike the `full_document` of the 23 files the owner viewed personally). `sopilot_eval.extraction --require-reviewed` green: 25/25 files. **Still open:** the furniture convention for the title "SOP Title: Deviations" (labelled furniture) differs from labeling/fda-qms-sop (not labelled); labels kept as is, the owner chooses one convention before boilerplate is scored in V2-21. Moved to `review`.

### Owner closes the ticket 2026-11-03
The owner set `done` on the evidence above (`--require-reviewed` gate green, 58 unit tests pass), accepting the Opus review instead of re-reading it. The furniture convention for the title 'SOP Title: Deviations' is still open and handled in V2-21.
