---
id: V2-18
title: "Research report and handover package"
type: docs
status: todo
created: 2026-10-17
updated: 2026-11-14
author: "Owner"
scope: docs
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-04, V2-07, V2-14, V2-17, V2-27, V2-28, V2-35, V2-37]
blocks: []
branch: "docs/docs-research-handover"
assignee: owner
---

# TICKET V2-18: Research handover

> Translated from Vietnamese on 2026-11-13; content unchanged. Report paths are given as originally planned; since the docs restructure, research reports live in `docs/research/` and acceptance reports in `docs/quality/test-reports/`.

## 1. Context & goal
Package everything so the assessor can rerun the results.

## 2. Acceptance criteria
- [ ] A report answering RQ1–RQ3 (and RQ4, RQ5 if available) with numbers from `eval/results/`, with limits: data scale, the human review process for questions, hardware, what was not measured.
- [ ] The NFR targets (recall@5 ≥ 0.80...) settled against the baseline, stating honestly whether each is met.
- [ ] Reproduction instructions for every table of numbers with the exact commands, recording the commit and configuration hash.
- [ ] A list of limitations and future work (rerank, deployment B1/B3, groups, ...).
- [ ] The handover package: source code, README, dataset or download script, results, the report in `docs/research/`; no secrets or `.env`.
- [ ] PLAN-V2: every other ticket `done` (36 of 37 as of 2026-11-14), the V2-18 report reviewed before moving to `done`; after acceptance the PLAN is 37/37 with matching counters (changed 2026-10-21: `V2-28` added; 2026-11-14: count updated to the current 37 tickets, and the items in §2b are finished or recorded as not measured). The report presents the results of `V2-28`'s Vietnamese SOP check set as a supplement, not as RQ results.

## 2b. Carried over from closed tickets (2026-11-14)
The owner closed these tickets as `done` on 2026-11-14 with criteria still open (each ticket's section 2a, "Closure"). Each item is either finished before this report or recorded in it as not measured.
- **`V2-28`:** owner review of the Vietnamese SOP question set and the licences of its 6 documents; agree the size and the 0.8 pass threshold; the real run on the local stack (`dev` to settle `doc_code_boost`, `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_FOLLOWUP_MAX_TOKENS`, then `test`); `gold_in_context` and the gap-list rate in the harness; the final report. Without the real run, the report presents no `V2-28` results.
- **`V2-25`:** p50/p95 of `t_upload_ack`, `t_ready`, `t_suggest` on the V2-19 corpus with an empty embedding cache.
- **`V2-16`:** a clean-environment try (time from clone to the first answer); TTFT P50/P95 with `scripts/measure-ttft.ps1` on the real provider (target P95 < 3 s, recorded as met or not); one question with citations through the API on the compose stack.
- **`V2-27`:** owner review of the routing set and examples; tune thresholds on `dev`, rerun `test` and decide on enabling `SOPILOT_SEMANTIC_ROUTER_ENABLED`; measure `followup` through `qa/pipeline.py`.

## 3. Guide
- **Files:** `docs/research/audit-v2-final-<date>.md`, `docs/research/research-report-v2.md` (CREATE). Author "Owner".

## 4. Testing
Someone else (or a clean environment) reruns the commands in the instructions and gets matching numbers.
