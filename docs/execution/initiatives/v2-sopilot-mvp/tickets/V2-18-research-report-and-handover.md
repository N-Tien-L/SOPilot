---
id: V2-18
title: "Research report and handover package"
type: docs
status: todo
created: 2026-10-17
updated: 2026-11-13
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
- [ ] The handover package: source code, README, dataset or download script, results, the report in `docs/04-reports/`; no secrets or `.env`.
- [ ] PLAN-V2: the remaining 32 tickets `done`, the V2-18 report reviewed before moving to `done`; after acceptance the PLAN is 33/33 with matching counters (changed 2026-10-21: `V2-28` added). The report presents the results of `V2-28`'s Vietnamese SOP check set as a supplement, not as RQ results.

## 3. Guide
- **Files:** `docs/research/audit-v2-final-<date>.md`, `docs/research/research-report-v2.md` (CREATE). Author "Owner".

## 4. Testing
Someone else (or a clean environment) reruns the commands in the instructions and gets matching numbers.
