---
id: V2-05
title: "Retrieval eval harness (FR-18)"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-07, V2-27]
branch: "feat/tests-eval-harness"
assignee: pair
---

# TICKET V2-05: Retrieval eval harness

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
An independent harness in `eval/`, running dense, BM25, hybrid (RRF) and rerank, without an LLM or the stack. Serves RQ1–RQ3, RQ5.

## 2. Acceptance criteria
- [x] `python -m sopilot_eval.run` runs with a dataset + config and writes `run.json`, `metrics.json`, `per_question.jsonl`, `report.md`.
- [x] Metrics: recall@k, hit@k, MRR, nDCG@10, latency p50/p95, a refusal-threshold sweep.
- [x] Embedding cache keyed by `(model, sha256(text))`.
- [x] 5 tests pass (`uv run pytest` in `eval/`).
- [x] A real run with `bge-m3` and `bge-reranker-v2-m3` on the owner's machine, confirming the `rq1-rq3-bge-m3.yaml` configuration runs (CPU). Evidence in §4.
- [x] The HF commit-hash `revision` pinned in the configuration: `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`, `BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` (the `main` versions on HF on 2026-10-20); `run.json` records the revision.
- [x] Baseline review by Codex on 2026-10-24; bugs found and fixed in AUDIT readiness.
- [x] The delta has had a technical review; the owner settled the acceptance scope on 2026-10-25; the changes were packaged with the acceptance commit.

## 3. Guide
Implemented: `eval/sopilot_eval/{corpus,embedders,retrievers,metrics,run}.py`, `eval/configs/`, `eval/datasets/smoke/`, `eval/tests/test_eval.py`, `eval/README.md`.

Not yet (recorded, not blocking this ticket): RQ4 (tenant filtering) belongs to V2-14; answer-level measurement (citation precision, faithfulness) needs an LLM and belongs to V2-10/V2-07.

## 4. Testing
```powershell
cd eval; uv sync --extra dev; uv run pytest -q
uv run python -m sopilot_eval.run --dataset datasets/smoke --config configs/smoke.yaml
```
Result 2026-10-17: 5 passed; the smoke run wrote all 4 files. The smoke numbers (hash embedder, 2 documents) have **no research value**.

Real run 2026-10-20 (owner's machine: AMD Ryzen, 16 threads, CPU, torch 2.14.1+cpu, sentence-transformers 6.1.0):
```powershell
cd eval; uv sync --extra local --extra dev; uv run pytest -q   # 5 passed
uv run python -m sopilot_eval.run --dataset datasets/smoke --config configs/rq1-rq3-bge-m3.yaml
```
- Run `20261020-140634`: all 5 configurations (dense, bm25, hybrid, hybrid-legacy-w, hybrid-rerank), all 4 files written. 35 minutes in total, mostly downloading `bge-reranker-v2-m3` (~2 GB, HF not signed in); `bge-m3` was already cached. The smoke numbers (3 chunks, 9 questions) only confirm it runs; **not reported**.
- CPU speed measured separately (passages of ~800 characters): `bge-m3` embedding about 0.41 s/chunk (64 chunks, batch 16; cached, so paid once); reranking 25 candidates takes about 10.5–11 s per question.
- Consequence for V2-07: 200 questions × a rerank pool of 25 ≈ 35–40 minutes per rerank configuration run, acceptable for eval. Too slow for interactive demos: keep `RERANK_ENABLED=false` by default or shrink the pool (TECH-V2-ai-service §11 Q3).
- Remaining: code review by someone else.

### Review 2026-10-24
Fixed nDCG to discount duplicates, splitter limits/parameter checks, the refuse-all threshold, the cache namespace, the reranker cache, wrong configurations and the run id. The report states that the gold is a document/page proxy, not span gold yet; no silent fallback to `docproc`. Commands/tests and limits in [AUDIT readiness](../../../../archive/reports/AUDIT-v2-readiness-preparation-2026-10-24.md). Kept `review` because the delta was not yet committed/peer-reviewed; heavy models and the official RQs were not rerun in this round.

### Acceptance 2026-10-25
The owner settled the scope in chat ("ok chốt"). Accepts the retrieval benchmark tooling, not the RQ results or the whole system. The delta review and the 18 tests in the commit's scope pass; the official RQs still belong to V2-06/V2-07/V2-22. See the [acceptance record](../../../../quality/test-reports/audit-v2-05-v2-08-acceptance-2026-10-25.md).
