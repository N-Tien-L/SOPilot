---
id: AUDIT-vi-sop-system-check-2026-11-13
title: "Vietnamese SOP system check set (V2-28): data checked, pipeline not yet run"
type: audit
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [tests, ai-qa]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-28-vi-sop-system-check.md
  - eval/README.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged.

# Vietnamese SOP system check set (V2-28)

> **These are not RQ results** and are not used to choose RQ3 thresholds (those belong to `V2-07`). The sample is small (33 hand-written questions + 4 auto-generated diacritic-free questions = 37), not enough for a statistical conclusion.
>
> **Conclusion:** `PASSED_WITH_WARNINGS` **only for the data and harness checks**. The pipeline has not run on this set, so **which groups pass is not known yet**; items (a)–(i) in §3 are all "not measured".

## 1. Scope done

| Part | Status |
|---|---|
| The question set `eval/datasets/vi-sop-check/` (gitignored): 33 questions, 33 gold spans, 6 documents (`SOURCES.md`, `manifest.json` with sha256) | Draft, `review_status: draft`, **not yet owner-reviewed**; document licenses pending the owner |
| Group e generated automatically (`generate_group_e`, seed `vi-sop-check-group-e-v1`) | Yes, with unit tests |
| Runner `eval/sopilot_eval/system_check.py`, config `eval/configs/vi-sop-check.yaml` | Yes. A real run calls `QAService.answer` (the real path, `qa/pipeline.py`); tests use a fake asker |
| Metrics by group and `query_types` (citation precision, gold spans cited, correct refusals, correct `refusal_reason`, PII masking) | Yes |
| `gold_in_context`, the correct gap-list rate | **Not yet**: `ServiceAsker` does not return `context_spans` yet; the gap list (V2-13) is not wired into the runner |
| Settling `doc_code_boost`, `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_FOLLOWUP_MAX_TOKENS` on `dev` | **Not yet**: the runner only records the values in the report and does not apply them |

## 2. Commands run (2026-11-13)

| Command | Result |
|---|---|
| `cd eval; uv run python -m sopilot_eval.system_check --config configs/vi-sop-check.yaml --dry-run` | Data valid (schema, span offsets and sha256 against the corpus, `dev`/`test` split, group sizes). 33 questions + 4 group-e questions; each group 2 `dev` + 2 `test`, except group h with 3 `test`. No service called |
| `cd eval; uv run pytest -q` | see the test run results of the Wave 1 closing round (ticket V2-28 §2a) |

## 3. Results by group

| Group | Checks | Result |
|---|---|---|
| (a) a merged "Trách nhiệm" (Responsibility) cell | `cell_spans`, `PROCEDURE_STEP` chunks | not measured |
| (b) a condition/exception at the start of a section | §6.4a context assembly | not measured |
| (c) lookup by document code | `doc_code_boost` | not measured |
| (d) issue number, effective date, approver | `<source code rev effective>` | not measured |
| (e) diacritic-free variants | `~` terms | not measured |
| (f) 1–2-page documents | the header/footer rule | not measured |
| (g) situational questions | | not measured |
| (h) off-topic, meaningless, too long, follow-up | `refusal_reason` | not measured |
| (i) questions with PII | masking before the LLM | not measured |

## 4. What the owner needs to do to get results

1. Review each question, answer, span and label (especially h04 expecting `INPUT_INVALID`, and i01–i04 which only check PII masking); confirm the size of 37 questions and the proposed pass threshold of 0.8 per group.
2. Confirm the licenses of the 6 documents in `SOURCES.md` (for documents that may not be redistributed, commit only the manifest and a download script).
3. Run for real on the local stack with a warmed-up Modal endpoint: load the 6 documents into a workspace, fill `principal` and `document_ids` in a separate config copy (do not commit the ids), run `--split dev` to settle the three parameters, then `--split test`, and update this report with the numbers, hardware and commit.

## 5. Not verified

All the Q&A metrics in §3; `gold_in_context`; the gap list; tuning the three parameters on `dev`.
