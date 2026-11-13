---
id: V2-37
title: "Retrieval configuration matrix and answer-level eval with an independent judge"
type: test
status: todo
created: 2026-11-11
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-07, V2-10, V2-13, V2-27, V2-35]
blocks: [V2-18]
branch: "test/eval-config-matrix"
assignee: pair
---

# TICKET V2-37: Retrieval configuration matrix and answer-level eval

> **Scope:** `tests` | **Size:** `L` | **Priority:** `P0`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `test/eval-config-matrix`

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal

Owner decision 2026-11-11 (note in [PLAN-V2](../PLAN.md)). RQ1–RQ5 retrieval numbers exist ([AUDIT-eval-rq1-rq3](../../../../research/audit-eval-rq1-rq3-2026-11-04.md) §12, [V2-35](V2-35-infra-modal-rerank-shared-gpu.md) results section). The research report still lacks:

- **answer-level** numbers on `sop-main-v2`. V2-10's `answers` run covered only `sop-main`, and the generation model graded itself (`judge_is_the_answer_model: true`);
- a measure of **correctness against `reference_answer`**. `answers.py` currently measures only faithfulness to the context;
- a controlled argument for the proposed configuration. On `sop-main-v2` test, dense + rerank and hybrid + rerank cannot be told apart (0.953 / 0.953 / 0.958; the CI contains 0);
- a comparison of the harness with the real API at answer level. The harness does not go through the guard, router, PII, rewrite, access filtering or output guard.

**Proposed configuration:** `hybrid`, RRF `k = 60`, weights 1/1, rerank `bge-reranker-v2-m3` (Modal), pool 25. This is the existing default in `services/ai-service/config/models.yaml` when rerank is enabled. No retriever code change.

**Hypotheses and decision rules (recorded before running, not changed after seeing test numbers):**
- H1 (non-inferiority): hybrid + rerank's `span_recall@5` is not worse than the best configuration in the matrix by more than δ = 0.02. The lower bound of the 95% CI of the paired difference must be > −0.02.
- H2 (superiority over no rerank): hybrid + rerank beats dense and hybrid at retrieval level, and beats dense on answer correctness. The 95% CI of the paired difference must be > 0.
- H3 (the role of BM25): in the groups of questions with document codes, without diacritics, and with exact numbers/terms, hybrid + rerank ≥ dense + rerank. If H3 fails, the report states that dense + rerank is simpler with equal scores.
- Multiple pairwise comparisons use the Holm correction. Negative results are reported in full.

## 2. Acceptance criteria

### A. Preparation
- [ ] Back up `eval/datasets/` and `eval/results/` outside the repo (both directories are gitignored). Record the location and the SHA-256 of the archive in the ticket.
- [ ] Reconcile hybrid `sop-main-v2` test: the AUDIT records `span_recall@5` 0.803, V2-35 records "recall@5 0.835". State whether these are two different measures or an error.
- [ ] Harness/service parity through Postgres on `sop-main-v2` (`service_parity --split all`). Mean top-10 Jaccard ≥ 0.95.

### B. Retrieval matrix (harness, `sop-main-v2`, dev + test)
- [ ] Six configurations: BM25, dense, hybrid 1/1, hybrid 0.7/0.3, dense + rerank, hybrid 1/1 + rerank. Same bge-m3 (pinned revision), `docproc` chunks, k = 5.
- [ ] Sensitivity of hybrid + rerank: `rrf_k` ∈ {20, 60, 100} × pool ∈ {10, 25, 50}.
- [ ] A derived set `datasets/sop-main-v2-probe`, without modifying the frozen set. Containing: (i) diacritic-free variants **generated automatically** from the test questions; (ii) a group of questions naming a document code, tagged from the v1 questions; (iii) a group of questions with exact numbers/terms, tagged by rule. Reported as a secondary analysis.
- [ ] Metrics: `span_recall@5`, `full@5`, `mrr_span`, p50/p95. Split by same-language / cross-lingual / probe group. Bootstrap clustered by `intent_id`. Paired differences with win/loss counts.

### C. Refusal thresholds
- [ ] Choose `thresholds.hybrid_rerank` (and `dense_rerank` if used) on **dev** with `analyze_v2_07`'s predefined rule (minimizing FR + FA). Apply unchanged to test. Not written into `models.yaml` until the owner approves.

### D. Judge
- [ ] A judge Modal app on an **L40S** (the second Modal account), one file parameterized by model: Gemma 4 26B A4B and Gemma 4 31B, FP8 checkpoints, `--max-model-len 8192`, FP8 KV cache, `max_containers=1`, 60 s idle. Record the HF revisions.
- [ ] The owner grades 30 answers first (correctness: correct / partial / wrong; faithfulness: grounded / partial / ungrounded), without seeing the judge's scores.
- [ ] The two Gemma models and Qwen self-grading (baseline) grade the same 30 answers. Record Cohen's κ (with CI), time, and the real cost from `modal billing report`.
- [ ] Choose the model with the higher κ; on a tie choose 26B A4B. If every model has κ < 0.6, the main numbers come from the human grader and the judge is only a reference.

### E. Answer level (harness `answers.py`, pinned QA commit)
- [ ] Pin the commit after `V2-13` and `V2-27` are done. Every run records `dirty: false`.
- [ ] `answers.py` gains: the GPU reranker, a correctness measure against `reference_answer`, citation recall, an independent judge. Unit tests with a fake LLM and judge.
- [ ] Trial run on 20 questions first. If the judge fails to parse more than 5%, stop and fix the prompt.
- [ ] Three configurations (dense, dense + rerank, hybrid + rerank) × 239 test questions, `temperature = 0`, `expand` on. Metrics: correctness, faithfulness, citation precision (hit level) and recall, answers without citations, false refusals (split between the retrieval gate and the LLM), wrong answers where it should refuse, the risk–coverage curve, p50/p95.
- [ ] A "closed-book" run (no context) on the answerable questions. Answers that are correct without documents are flagged, and faithfulness is reported split by the flag.
- [ ] Three repeated runs at `temperature = 0.2` on 60 questions fixed by hash. Report the share of answers that change between runs.
- [ ] The owner grades 30 more answers (60 in total). Report the final κ between the chosen judge and the owner.

### F. Comparison with the real API
- [ ] A runner calls `POST /ai/v1/conversations/.../messages` (core-api JWT, reading SSE) with core-api, ai-service and the worker running locally. Documents uploaded through core-api. Gold spans remapped by `quote`.
- [ ] About 30 test questions run through both the harness and the API with the same configuration. Report the difference in outcome, citations and correctness. If the difference exceeds the harness CI, investigate before reporting.

### G. Budget and report
- [ ] The answer-generation Modal account ≤ $15; the judge account ≤ $8. Record the real cost after each step. If a cap is exceeded, stop and ask the owner.
- [ ] Raw results stored in `eval/results/<run_id>/`. Report `docs/research/audit-eval-config-matrix-answers-<date>.md`: hypotheses, decision rules, tables with CIs, unfavourable results, limitations (LLM-drafted labels, 23 documents, a small judge, Vietnamese not on the Gemma 4 model card).
- [ ] `eval` pytest green; `./scripts/check-docs.ps1` green.

## 3. Guide

- **Do not send documents to external APIs.** The judge runs only on the owner's Modal. Gemini is not used for the main grading: only 104/200 test questions have evidence from documents allowed to be sent out, and the context may contain chunks of restricted documents (`manifest.json`, `redistribution`).
- **Labels:** keep `review.jsonl` unchanged. The report states the process accurately: questions drafted by an LLM (`drafted_by`), 105 v1 questions reviewed directly by the owner, 188 v2 questions reviewed by the owner on the basis of Claude's review pass (`review_basis=claude_review`).
- Reuse `sopilot_eval.run`, `analyze_v2_07`, `answers`, `service_parity`. Do not copy pipeline logic into the harness.
- No new dependency. `httpx` is already available through the `services/ai-service` path dependency.
- Order: A → B (in the background) → C → D → E → F → G.

## 4. Testing

| Kind | Content | Command |
|---|---|---|
| Unit | Correctness measure, citation recall, verdict parsing, diacritic-free variant generation, the threshold selection rule, κ | `cd eval; uv run pytest -q` |
| Manual | Retrieval matrix, `answers`, judge, API comparison | Commands and run ids recorded in section 6 |

## 5. Changed files

| File | Action |
|---|:---:|
| `eval/sopilot_eval/answers.py` | MODIFY |
| `eval/sopilot_eval/system_api.py` (runner calling the real API) | CREATE |
| `eval/sopilot_eval/probe.py` (the derived set) | CREATE |
| `eval/configs/v2-37-matrix.yaml`, `v2-37-sensitivity.yaml`, `v2-37-answers.yaml` | CREATE |
| `infrastructure/modal/serve_judge.py` | CREATE |
| `eval/tests/test_v2_37_*.py` | CREATE |
| `docs/research/audit-eval-config-matrix-answers-<date>.md` | CREATE |

## 6. Results

*(Fill in when running: run id, commit, real cost.)*
