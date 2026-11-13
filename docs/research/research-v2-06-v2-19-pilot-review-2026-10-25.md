---
id: RESEARCH-V2-06-V2-19-PILOT-REVIEW-2026-10-25
title: "V2-06/V2-19 real-data pilot and the label package awaiting owner review"
status: final
created: 2026-10-25
updated: 2026-11-13
type: research
scope: tests
author: "Owner"
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-06-multilingual-eval-dataset.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-19-sop-extraction-corpus.md
  - docs/archive/reports/AUDIT-v2-readiness-preparation-2026-10-24.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. Ticket statuses mentioned here are as they were on 2026-10-25 (`in-progress` is now `in_progress`).

# Pilot round results

The owner asked to carry out the proposal: prioritize the small V2-19 PDF set and prepare the V2-06 pilot at the same time. This round has real data and concrete label sheets to review. `final` means the pilot handover is complete, **not acceptance of the two tickets/corpora or of research results**. Both tickets stay `in-progress` and the PLAN counters/DAG are unchanged.

Work continued on the `chore/tests-v2-readiness` checkout, which already had preparation changes; no stash/reset, branch switch, commit or push. No change to V1/V2 services, DB, API, events or RBAC. The existing PRD/TECH/harness/infrastructure changes were kept. The build scope is `eval/`; `validate-build.ps1` has no eval scope, so pytest, ruff and compileall were used directly.

## 1. V2-19: original PDFs obtained

| Group | Files | Pages | pypdf result without OCR |
|---|---:|---:|---|
| ISO VI: Ninh Binh Department of Construction QT-01/02/03/04 | 4 | 44 | Text present; each PDF has a first page without text |
| ISO VI: Thai Binh Port Authority QT.01/03/05 | 3 | 34 | Every page has text |
| ISO VI: Ninh Binh Inspectorate QT 06/TTr | 1 | 17 | Every page has text |
| EN EPA SOP: Soil Sampling / Field Sampling QC | 2 | 53 | Every page has text |
| Decree 30 (NĐ 30), digitally signed | 1 | 76 | No characters extracted on any of the 76 pages; the page 1 image is a scan |
| **Total** | **11** | **224** | No Docling measurements yet |

Sources and hashes are in [SOURCES](../../datasets/extraction/SOURCES.md) and the [acquisition lock](../../datasets/extraction/pilot/acquisition.lock.json). PDF bytes are kept unchanged; the URL/final URL, MIME type, UTC time, SHA-256 and a per-page probe are recorded. The PDFs and page images live in the gitignored `local/` area because redistribution rights have not been verified per document; government documents are not assumed to be CC/public domain. No OCR and no PDFs generated from HTML.

Selected pages were rendered with Poppler and the images read to draft labels: headings, table/fragment positions, horizontally merged cells and QT-01's nested table, metadata, boilerplate and some references. **10 records are partial labels (`selected_pages`), 1 record is only a `NO_TEXT_LAYER` refusal expectation.** Unconfirmed header tables are recorded as `pending_fields`, without guessed column names. The issue date of VI SOPs is not assigned as the effective date; the EPA QC revision is taken from the R7 content, not the r5 filename.

The minimal candidate set: nb-qt01/02/03/04, tb-qt01/03, epa-soil/qc, nd30. Enough files to start preparing but not enough owner-reviewed labels for the V2-19 gate. Fragment labels are not treated as whole-document gold. The scorer blocks scoring a whole document with partial labels and does not let refusal cases count towards heading/table scores.

Open the [PDF review sheet](../../datasets/extraction/pilot/REVIEW.md). Next after the pilot: complete the labels for the remaining pages/the representation of tables spanning pages, settle usage rights, extend to 20–50 files/5 families, 1–2-page PDFs, and add scans/MD. Time/RAM and Docling quality are not measured yet; pypdf measurements do not replace `V2-20`.

## 2. V2-06: bilingual pilot on real sources

- 4 documents: 2 VI PDF SOPs (`nb-qt02`, `nb-qt03`) and 2 EN GitLab pages (Buddies, Meetings).
- GitLab is pinned to commit `4684d72f27f3401d3ae72a26d72ae46eaeaab929`; the raw files and the license evidence page were downloaded at the same commit. GitLab text/adaptations keep the attribution and CC-BY-SA-4.0; the code repo license is not substituted.
- 12 intents / 24 questions drafted by Codex: 12 VI, 12 EN; 20 answerable, 4 negative; 12 cross-lingual in both VI→EN and EN→VI; 16 spans with AND evidence; covering 7 `query_types`.
- 24 questions kept at the pilot creation stage, 0 removed, **0 reviewed by a person**. Every question is `draft`, all **dev**, no test or freeze. A translation is not counted as a separate intent.
- `expected` is derived from `evidence_sets`, not maintained in parallel by hand. Quotes/offsets/hashes point at the canonical text correctly; the page map uses physical page numbers.
- Negative questions have a draft agent audit against all four documents and candidate keywords; the owner still has to read the content to confirm. `review.jsonl` is empty, with no fake reviewer. When the corpus grows, the negative questions must be audited again.

Open the [review sheet for 12 intents/24 questions](../../eval/datasets/sop-pilot/REVIEW.md): each intent has VI/EN, two draft answers, evidence, offsets and source/page. The [README](../../eval/datasets/sop-pilot/README.md) records how to reproduce; [SOURCES](../../eval/datasets/sop-pilot/SOURCES.md) records attribution and distribution limits.

The current ticket's VI/EN scope is kept; the EN GitLab corpus design in the old handoff does not override that requirement. The pilot is a step to size the review effort and does not settle the final minimum scale (~100 per the ticket or another scale the owner approves). The VI canonical text is currently only a pypdf 6.21.0 inventory with NFC/whitespace normalization, not Docling structured Markdown. Before the official RQs, the corpus/spans must be rebased with the V2-20/V2-22 docproc, reviewed and versioned again; the span-aware/truncation scorer is still among the remaining tasks of the eval chain.

## 3. Tooling and checks

Two new modules: `eval/sopilot_eval/acquire.py` (pinned/hashed downloads, blocking paths escaping the dataset and HTML posing as PDF, a probe without OCR, offline verification) and `prepare_pilot.py` (section allowlist, canonical text/page map, spans and questions from a seed, never overwriting edited artifacts). Added 11 regression tests in `test_corpus_acquisition.py`; fixed a guard in the extraction scorer.

| Check | Evidence |
|---|---|
| `eval/.venv/Scripts/python.exe -m pytest -q eval/tests --basetemp=eval/.cache/pytest-corpus-final` | **37 passed** (11 new tests + 26 existing) |
| From `eval/`: ruff on acquire/prepare_pilot/extraction and test_corpus_acquisition | Pass |
| compileall on the 4 code/test files of this round | Pass |
| acquire both `sources.json` with `--offline` | 11 PDFs + 3 raw GitLab files match SHA-256, no network calls |
| prepare_pilot rerun on the same lock/seed | Pass; 4 documents, 16 spans, 24 questions; dev 24/test 0; no artifact replaced |
| Retrieval / extraction validators | Structural pass: 24 questions / 11 annotation records |
| Both validators with `--require-reviewed` | Exit 1 as expected: retrieval is draft; extraction labels are partial |
| `sopilot_eval.plan_check` | 33 tickets, 75 edges, counters/DAG/closure match |
| `git diff --check` | Pass; `git check-ignore` confirms the PDFs, raw cache and VI canonical text are not added to git |
| `scripts/pre-commit-check.ps1` | Pass; env-file auto-load disabled, an empty env file in the repo, random dummy values for the required Compose variables; `.env` not read, no stack run |

Running ruff on all of `eval/tests` from `eval/` still reports import order in two existing files, `test_harness_regressions.py` and `test_review_regressions.py`; nothing outside this round was changed. Lint of the files changed in this round passes. Pre-commit does not run eval tests itself and skips untracked files, so pytest/lint were run directly. No full stack, LLM/embedding API, Docling or RQ was run.

## 4. Points for owner review and next steps

1. Read the 12 intents in the V2-06 sheet; confirm/edit/remove each intent and translation, especially the negative questions and time conditions. This is the basis for settling the expansion scale and split groups, not a final test sign-off.
2. Compare the selected pages in the V2-19 sheet; confirm the representation of headings/nested tables/merged cells and metadata. The review applies only to the pages viewed; whole-document labels still have to be completed before corpus acceptance.
3. After feedback, record the real reviewer/date/review version; complete the PDF labels, extend the corpus and prepare the V2-20 Docling baseline. Do not change `review_status` or `done` just to make the tooling green.

Progress docs updated: V2-06, V2-19 and PLAN-V2; the dataset/eval guides gained the pilot paths. No product contract change, so `.agent/context/` is unchanged.
