---
id: V2-06
title: "Multilingual (VI, EN) corpus and reviewed question set"
type: docs
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-07, V2-09]
branch: "docs/tests-eval-dataset"
assignee: owner
---

# TICKET V2-06: Multilingual eval dataset

> Translated from Vietnamese on 2026-11-13; content unchanged. Unchecked criteria below were left unchecked in the original when the owner closed the ticket on 2026-11-03 (see "Owner closes the ticket").

## 1. Context & goal
The biggest bottleneck of the research part. It needs a public Vietnamese and English corpus, and questions labelled with the expected document/page, language, a cross-lingual flag, and unanswerable questions.

Per the PLAN's feasibility principle: the dataset size is decided by **the owner's capacity to review**, not set large and abandoned. A small, carefully reviewed set that runs is better than a large unreviewed one.

## 2. Acceptance criteria
- [x] Agree a minimum feasible size with the owner before starting. *(Owner decision 2026-11-01: ~100 questions as proposed; canonical text from docproc.)* Initial proposal (adjustable): ~10 documents per language; ~100 questions: ~35 VI, ~35 EN, ~15 cross-lingual (asked in one language, answer in a document of the other), ~15 unanswerable.
- [ ] Every document records its source and license in `datasets/<name>/SOURCES.md`; documents not licensed for redistribution do not enter the repo (commit a manifest + a download script).
- [ ] Every question has `lang`, `cross_lingual` (bool), `answerable`, `evidence_sets` (**span** gold, schema in [RESEARCH-02](../../../../04-reports/RESEARCH-02-dataset-and-labeling.md) §5.1 and §8), `reference_answer`; `expected` ({doc, pages}) is derived from `evidence_sets`, never entered twice. Changed 2026-10-21 (audit by query type): span gold is a precondition of the "share of gold spans in the context" metric in `V2-10`.
- [ ] Changed 2026-10-21 (owner decision D7/P0-6): add `query_types`, a list of labels (a question may have several) from the set `fact`, `procedure`, `condition_exception`, `number_deadline`, `responsibility`, `comparison`, `multi_passage`. Label the existing intents, without adding questions. The `V2-07` and `V2-10` reports split their numbers by these labels. **Must be done before freezing the test set** (before `V2-07`).
- [ ] Diverse questions: numeric lookups, multi-step procedures, questions needing several passages, wording different from the document's keywords.
- [ ] If an LLM drafts: the owner reviews each question; the report records the number generated and rejected.
- [ ] Split into dev (threshold tuning) and test (final report), never mixed.

## 3. Guide
- **Files:** `eval/datasets/<name>/corpus/`, `questions.jsonl`, `SOURCES.md`. Format in `eval/README.md`.
- The agent may gather public sources and draft; the owner reviews.

## 4. Testing
`uv run python -m sopilot_eval.run --dataset datasets/<name> --config configs/smoke.yaml` runs through without format errors and the report has a table split by `lang`.

### Preparation 2026-10-24 (data not yet accepted)
There is a validator `eval/sopilot_eval/dataset.py`, a schema/guide `eval/datasets/README.md`, and 5 draft EN/VI questions on a synthetic corpus in `eval/datasets/annotation-example/`. It checks offsets/quotes/hashes, AND/OR evidence, query labels and dev/test leakage. This is only a tooling example; the research corpus is not downloaded, the size is not settled, and there are no owner-reviewed labels. `--require-reviewed` must fail on the draft example. No data criterion is marked done.

### Real-source pilot 2026-10-25 (pending owner review)
At the owner's request to continue with proposals in chat: created `eval/datasets/sop-pilot/`, 4 real documents (2 Vietnamese PDF SOPs from V2-19, 2 English GitLab pages at the same commit), 12 intents / 24 draft questions written by Codex, 16 spans. 20 answerable questions, 4 negatives, 12 cross-lingual in both directions; all 7 `query_types` covered. All of it is **dev/draft**: 0 questions reviewed by a person, 0 rejected while building the pilot; no test set or freeze yet. The 24-question pilot measures review effort and does not settle the final minimum size by itself.

The ticket's VI/EN corpus requirement stands; the GitLab-only English corpus of an older handoff is a superseded option and does not replace this scope. GitLab is pinned to commit `4684d72f27f3401d3ae72a26d72ae46eaeaab929`, with CC-BY-SA-4.0 attribution stored. Vietnamese PDFs/canonical text whose redistribution rights are unclear are kept locally only, with a download script and hash lock. The PDF canonical text is currently a pypdf 6.21.0 inventory; spans/versions must be rebased onto docproc V2-20/V2-22 before the official RQs. Negatives need re-auditing when the corpus grows.

Review sheet of questions/answers/evidence: [pilot REVIEW](../../../../../eval/datasets/sop-pilot/REVIEW.md). Reproduction guide: [pilot README](../../../../../eval/datasets/sop-pilot/README.md). `prepare_pilot` and the validator pass; `--require-reviewed` must still fail. Kept `in-progress`; the data criteria are not accepted. Evidence and limits in the [pilot HANDOFF](../../../../04-reports/RESEARCH-V2-06-V2-19-pilot-review-2026-10-25.md).

### Owner reviews the pilot 2026-11-01 (ticket not yet accepted)
The owner reviewed all 24 pilot questions with the local app `eval/review_ui/server.py` (checking question, answer and span against the canonical text and the PDF page image): **24/24 `reviewed`**, 0 rejected, 0 edited in content/`query_types`/span, `reviewer_id=owner:tiên`. `review.jsonl` has 24 records matching `label_version`/`corpus_version`; the 4 negatives have an `unanswerable_audit` (the owner read all 4 pilot documents). `sopilot_eval.dataset --require-reviewed` is **green**. Drafting statistics: 24 questions generated (Codex), 0 rejected.

This is the reviewer gate of the **dev pilot**, not ticket acceptance: the minimum size is not settled, the corpus has only 4 documents (2 VI, 2 EN), there is no test set/freeze, and the Vietnamese canonical text is still a pypdf inventory to be rebased onto docproc before the official RQs. Negatives must be re-audited when the corpus grows. Kept `in-progress`.

### Main set sop-main 2026-11-01 (pending owner review of the test set)
The owner settled the scale at ~100 questions with canonical text from ai-service docproc. Created [`eval/datasets/sop-main/`](../../../../../eval/datasets/sop-main/README.md): **23 documents** (13 VI, 10 EN; 21 from the V2-19 corpus including Vietnamese ISO 9001, government documents, EPA, FDA, NCI GMP SOPs, Kubernetes; 2 GitLab pages), canonical text built by `eval/build_canonical.py` running `extract → clean_document → render` (Docling 2.142.1, CPU). **105 questions**: dev 24 (the pilot) + test 81 (new), 125 spans; 37 VI/VI, 38 EN/EN, 15 cross-lingual, 15 negatives; all 7 `query_types`; one question has two OR sets. Dev and test are split by document, policy group and span; the structural validator is green. The builder `sopilot_eval/prepare_main.py` (5 unit tests) reads `test.seed.json`, finds offsets by quote and rebases the pilot spans.

Review: 10 dev questions keep the owner's review because their quotes are byte-identical after the rebase (`carried_from` in `review.jsonl`); 14 dev questions go back to `draft` (10 GitLab questions changed quote format, 4 negatives need re-auditing because the corpus grew). **81 test questions drafted by Claude, 0 rejected while drafting, not yet reviewed by anyone**; `--require-reviewed` is red. Reviewed with `eval/review_ui/server.py` (opens `sop-main` by default).

Limits: the canonical text was built from docproc with uncommitted changes (`docproc_dirty=true` in the manifest); Docling loses tb-qt01 page 5's drafting/review/approval assignment table (a V2-20 bug; questions avoid that passage). The test set is not frozen; it is frozen after the owner finishes reviewing, before `V2-07`. Kept `in-progress`.

### Full review of sop-main 2026-11-03 (pending owner acceptance)
The owner asked Claude Opus 5.5 to review all the remaining questions for lack of time to read them; `review.jsonl` records `reviewer_id=owner:tiên` at the owner's direction, while `notes` state clearly that the review was done by Opus and **the owner has not re-read it**. Process: 7 Opus agents reviewed independently by document batch (EPA, FDA/NCI, GitLab/k8s, ISO Ninh Bình, ISO Thái Bình, Vietnamese documents, negatives), each reading only the region around the spans; 53/80 answerable questions needed fixes (mostly spans cut mid-sentence, figures and correct answers), 0 rejected; the fixes became structured patches with unique verbatim quotes checked, applied through `V206Store`. Then 2 independent Opus agents rechecked the 80 items (53 patched, 27 approved directly, 6 negatives re-grepped): 6 failed (a missing epa-sw OR set in 2 questions, truncated spans in 4) and were patched and reapplied. Content fixes: `epasoil-low-high-en` (answer: the 40 mL vial applies only when sampling by syringe), `qd1308-data-audit` (rewritten as the 2030 target), `tt06-retention` (added the QT 06/TTr Ninh Bình context). `qd1308-proposer`: the correct number is `319/TTr-BCA-C12` (see the page 1 image); the canonical text still has Docling's `BCAC12` error (V2-20's job).
Result: 105 questions `reviewed` (dev 24, test 81; the 15 negatives have an `unanswerable_audit`); `sopilot_eval.dataset --require-reviewed` green, 58 unit tests pass. Limits: trust rests on Opus, not a person; the test set is not frozen; the canonical text was built from docproc with uncommitted changes (`docproc_dirty=true`). Moved to `review`; `done` needs owner acceptance and a freeze before V2-07.

### Owner closes the ticket 2026-11-03
The owner set `done` on the evidence above (`--require-reviewed` gate green, 58 unit tests pass), accepting the Opus review instead of re-reading it. Remaining before V2-07: freeze the test set (not done yet) and rebase the canonical text once docproc is committed.

### Freeze 2026-11-04
At the owner's direction, Opus rebuilt the `sop-main` canonical text with the clean docproc commit `26d1ed1` (`docproc_dirty=false`) into a temporary folder and compared every span before applying. 17/23 documents changed text (the new docproc drops repeated headers, "Nơi nhận" (distribution)/national-motto blocks, header-only pages; tb-qt01 has its assignment table back). All 218 spans (144 in use: 128 test, 16 dev) still match their quotes verbatim: 94 keep their offsets, 124 shift (3 repeated quotes keep the right occurrence), **0 changed/lost**, and no span's page changed. Applied entirely with `corpus_version=sop-main-2026-11-04-v2`; questions, answers, `evidence_sets` and `review_status` unchanged; `review.jsonl` only changes `corpus_version` and adds `rebased_from`. Details: `eval/datasets/sop-main/rebase-report-2026-11-04.json` and the "Freeze 2026-11-04" section of the [README](../../../../../eval/datasets/sop-main/README.md).

Freeze: `manifest.json` `frozen=true`, `frozen_by="owner:tiên (Opus thực hiện theo chỉ đạo)"`, `frozen_docproc_commit=26d1ed1326cd37f8714b44e68929d784dc1659b9`, `test_sha256=f80c2e5d22a9d2f5454953135b61875630d55567ab9ec0f07e2feb8862102aaf` (81 test questions: id, question, answer, evidence_sets with spans and `quote_sha`). `sopilot_eval/dataset.py` gains `fingerprint_test_split`, `check_frozen` (errors when the hash, `corpus_version` or docproc commit differ, or a test question is unreviewed) and `--freeze`; 10 unit tests in `eval/tests/test_dataset_freeze.py`. Evidence: `python -m sopilot_eval.dataset --dataset datasets/sop-main --require-reviewed` green (`frozen: true`), eval `pytest` 80 pass. Unfreezing only by hand-editing the manifest with a recorded reason (README). Limits: `eval/datasets/` is not in git, so the owner must back up the `sop-main` folder separately; the negatives' `candidate_sections` are still counted on the old version.
