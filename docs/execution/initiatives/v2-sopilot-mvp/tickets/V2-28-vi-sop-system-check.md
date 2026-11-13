---
id: V2-28
title: "Vietnamese SOP system check set (30–40 questions): merged cells, context assembly, document codes, validity, no diacritics"
type: test
status: review
created: 2026-10-21
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P1
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-19, V2-21, V2-22]
blocks: [V2-18]
branch: "test/tests-vi-sop-system-check"
assignee: owner
---

# TICKET V2-28: Vietnamese SOP system check set

> Translated from Vietnamese on 2026-11-13; content unchanged. The report path `docs/04-reports/` is as it was at the time.

## 1. Context & goal
Owner decision 2026-10-21 (end-to-end audit of ai-service by query type, D7; see [PLAN-V2](../PLAN.md)). `V2-06`'s RQ corpus is English GitLab Markdown; its Vietnamese questions are all VI→EN. So `PROCEDURE_STEP` chunks, Điều/Khoản (article/clause) texts, section-based context assembly (TECH-V2-ai-service §6.4a), document codes, metadata in `<source>` and diacritic-free terms have **never been measured on real Vietnamese SOPs**; `V2-19` measures only extraction, not Q&A.

This is a **system check** set to accept the audit's changes, not an RQ experiment, and it is not used to choose RQ3 thresholds (those belong to `V2-07`).

## 2. Acceptance criteria
- [ ] Agree the size with the owner according to review capacity (proposed 30–40 Vietnamese questions) on owner-reviewed `V2-19` files: ISO SOPs with procedure tables and merged cells, Điều/Khoản texts, documents with effective dates and codes, 1–2-page PDFs. Same schema as `V2-06` (span `evidence_sets`, `query_types`, `reference_answer`), split into `dev`/`test`.
- [ ] Cover the groups, each with passing and easy-to-fail questions:
  - (a) a merged "Trách nhiệm" (Responsibility) cell: "bước 3 ai làm" (who does step 3; checks `cell_spans` and `PROCEDURE_STEP` chunks);
  - (b) a condition or exception at the start of a section (checks §6.4a context assembly);
  - (c) lookup by document code ("QT-MH-01 bước 2 ai duyệt" (who approves step 2 of QT-MH-01); checks `doc_code_boost`);
  - (d) issue number, effective date, approver (checks `<source code rev effective>`);
  - (e) diacritic-free variants **generated automatically** from the existing questions (checks `~` terms);
  - (f) 1–2-page documents (checks the header/footer rule);
  - (g) situational questions with specific facts;
  - (h) off-topic, meaningless, over-1000-character and follow-up questions (checks `refusal_reason` and whether the question enters the gap list);
  - (i) questions containing PII (checks masking before sending to the LLM and in the gap list).
- [ ] A runner executes the real `V2-10` pipeline on the local stack and DB (a fixed LLM, `temperature=0`; parts not needing generation run with a fake LLM). Reported by group (a)–(i) and by `query_types`: the share of gold spans in the context, citation precision, the correct refusal rate, correct `refusal_reason`, the correct gap-list rate.
- [ ] Use the `dev` set to settle the still-open starting values: `retrieval.doc_code_boost`, `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_FOLLOWUP_MAX_TOKENS`; `test` numbers are only for reporting.
- [ ] Report `docs/04-reports/AUDIT-vi-sop-system-check-<date>.md`: which groups pass or not, the causes, next proposals (for example the `DOC_INFO` chunk or opening §6.4a, per TECH-V2-ai-service §12a). State clearly that these are not RQ results and the sample is small.

## 2a. Evidence and open items (2026-11-13)
- Harness: `eval/sopilot_eval/system_check.py`, `eval/configs/vi-sop-check.yaml`, `eval/tests/test_vi_sop_check.py`. The runner calls the real `QAService.answer`; group e is generated automatically with a fixed seed.
- The draft question set `eval/datasets/vi-sop-check/` (gitignored): 33 questions + 4 group-e questions = 37, 33 spans, 6 documents; `--dry-run` on 2026-11-13 is valid. Report: [AUDIT-vi-sop-system-check-2026-11-13](../../../../04-reports/AUDIT-vi-sop-system-check-2026-11-13.md) (`draft`, not RQ results, small sample, **pipeline not yet run**).
- **Still open (owner):** review every question and the licenses of the 6 documents; agree the size and the 0.8 pass threshold; run for real on the local stack with Modal (`dev` to settle `doc_code_boost`, `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_FOLLOWUP_MAX_TOKENS`, then `test`). Missing in the harness: `gold_in_context` (the asker does not return the context spans yet) and the gap-list rate.

## 3. Guide
- **Files:** `eval/datasets/vi-sop-check/` (questions, labels, `SOURCES.md`), `eval/sopilot_eval/system_check.py`, `eval/configs/vi-sop-check.yaml`. Documents that may not be redistributed: commit a manifest and download script, not the files.
- The agent may draft questions; the owner reviews each one (as in `V2-06`).
- Call the `qa/pipeline.py` pipeline directly; do not copy logic into the harness.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | Dataset format, diacritic-free variant generation, per-group metrics | `uv run pytest` in `eval/` |
| Manual | Run on `test` with the local stack, attach the report | `python -m sopilot_eval.system_check --config eval/configs/vi-sop-check.yaml` |
