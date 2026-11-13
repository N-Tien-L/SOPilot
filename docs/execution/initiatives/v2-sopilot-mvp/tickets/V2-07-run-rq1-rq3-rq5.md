---
id: V2-07
title: "Run RQ1–RQ3 and RQ5, write the report"
type: docs
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-05, V2-06, V2-22]
blocks: [V2-18, V2-37]
branch: "docs/tests-eval-report"
assignee: pair
---

# TICKET V2-07: Run the experiments

> Translated from Vietnamese on 2026-11-13; content unchanged. The report path `docs/04-reports/` is as it was at the time.

## 1. Context & goal
The decision gate: multilingual retrieval numbers tell whether RAG is worth further investment. The NFR targets (recall@5 ≥ 0.80...) may be adjusted from the baseline.

Per the feasibility principle: **run each configuration for real on the owner's machine first, then put it in the matrix**. A configuration that cannot run on CPU in reasonable time runs on a subset or is dropped, and the report states why. No configuration is promised to be in the report in advance.

Changed 2026-10-21 (pre-implementation review, TECH-V2-ai-service §6.5): the official numbers run with `V2-22`'s `sopilot_ai.docproc` chunker so the results and thresholds apply to the service. Smoke and exploratory runs with the existing 800/100-character chunker can still run before `V2-22`, but are not reported as official numbers.

## 2. Acceptance criteria
- [x] The official RQ configuration uses `chunking: docproc` (target 384 / max 512 tokens, the tokenizer of the model measured, like ai-service's `config/models.yaml`); the report records the `docproc` version and `normalizer_version`. Results from the old chunker are labelled exploratory only.
- [x] Changed 2026-10-21 (audit by query type, owner decisions D11/P0-1/P0-6), **done before the official runs so nothing needs remeasuring**: (a) the harness implements TECH-V2-ai-service §6.3's final BM25 tokenizer (diacritic-free `~` terms) in `eval/sopilot_eval/retrievers.py::tokenize`; (b) the harness's `hybrid` gate uses an always-present `dense_score`: a top candidate with only a BM25 score gets its cosine computed directly (TECH-V2-ai-service §6.4, [RESEARCH-04](../../../../04-reports/RESEARCH-04-experiment-tooling.md) §5), because RQ3 measures the threshold on exactly this score; (c) `V2-06` has labelled `query_types` and frozen the test set. The report splits numbers by `query_types`.
- [x] Smoke-measure the time and RAM of `bge-m3` and `bge-reranker-v2-m3` on the owner's machine with ~50 chunks; decide which configurations enter the matrix from the measurements.
- [x] RQ1/RQ1b: dense, bm25, hybrid (both weightings 1/1 and 0.7/0.3) with pinned `bge-m3`, on the test set, **reported by `lang` and by cross-lingual**.
- [x] Changed 2026-10-21 (TECH-V2-ai-service §6.4): if hybrid loses to dense on the cross-lingual group, also run hybrid with `cross_lingual_bm25_factor` ∈ {0.3, 0} (the harness implements this factor in its own RRF until `V2-09` has `retrieval.fusion`); choose the value on dev, report on test, record it in `retrieval.cross_lingual_bm25_factor`. If it does not lose, keep `1.0` and record why. **(Decided 2026-11-07: keep `1.0`. The dev rule chose 0.3 but by only 1 question, test shows no difference, and the factor does not address the cause; see the report §4.2, §12.)**
- [x] RQ2: rerank on/off, k ∈ {5, 10}, with latency; if too slow on CPU, run on a fixed subset and say so.
- [x] RQ3: the false refusal / false answer trade-off; the threshold chosen on dev and measured on test. The chosen thresholds are written to ai-service's `retrieval.thresholds` per mode (TECH-V2-ai-service §6.4). **(Decided 2026-11-07: a deliberate deviation, not written. The thresholds chosen on dev do not transfer to test, FA on test 0.36 to 0.56, because dev has only 14 negatives; the placeholders stay in `models.yaml` and are calibrated in V2-10.)**
- [x] RQ5: compare only the models that run on the machine (candidates: `bge-m3`, `Qwen3-Embedding-0.6B`, `multilingual-e5-large-instruct`; e5 limited to 512 tokens). Record each model's corpus embedding time.
- [x] Record the hardware (CPU, RAM); latency over ≥ 3 runs, with the spread.
- [x] State the limits: small data scale, simple BM25 tokenization (no per-language tokenizer), retrieval only if V2-10 is not done.
- [x] Report `docs/04-reports/AUDIT-eval-rq1-rq3-<date>.md` pointing to `eval/results/<run_id>/`.

## 3. Guide
`uv sync --extra local` then `uv run python -m sopilot_eval.run --dataset ... --config configs/rq1-rq3-bge-m3.yaml`. Add RQ5 configurations to `eval/configs/` after the smoke measurement. `eval/pyproject.toml` declares `services/ai-service` as a path dependency to import `sopilot_ai.docproc`.

## 4. Testing
Rerunning the same configuration must give the same retrieval ranks (PRD reproducibility NFR).

## 5. Progress 2026-11-04

The official numbers have run; report [AUDIT-eval-rq1-rq3-2026-11-04](../../../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) (`draft`). Harness code committed in `583d0a3`.

- [x] `docproc` chunks (target 384 / max 512, each model's tokenizer) through `sopilot_ai.docproc` (path dependency in `eval/pyproject.toml`); 23/23 documents rebuilt byte-identical to the frozen corpus. `normalizer_version=2`, corpus from docproc `26d1ed1`.
- [x] (a) BM25 tokenizer with `~` terms (`retrievers.tokenize`, `lexical_len`); (b) the `hybrid` gate uses an always-present `dense_score`, `bm25` has no gate, rerank uses a sigmoid; (c) the report is split by `query_types`. Tests: `eval/tests/test_v2_07_retrieval.py`.
- [x] Smoke of bge-m3 / bge-reranker-v2-m3 / Qwen3-Embedding-0.6B / e5-large-instruct (`sopilot_eval.smoke_models`); all four enter the matrix, rerank runs with its own configuration file.
- [x] RQ1 split by `lang` and cross-lingual; RQ1b ran the factor {0.3; 0}: dev chose 0.3 (by 1 question), test shows no difference. **Not yet written** to `retrieval.cross_lingual_bm25_factor`: waiting for the owner (ai-service had no `models.yaml` yet).
- [x] RQ2: rerank on/off, k ∈ {5, 10}, on both dev and test (no subset needed), 3 runs; p50 17.7 s/question on CPU.
- [x] RQ3: threshold chosen on dev, measured on test. **Not yet written** to `retrieval.thresholds`: waiting for the owner.
- [x] RQ5: three models, with corpus embedding times.
- [x] Hardware, latency over 3 runs with the spread, limits.
- [x] Reproducibility: rerunning the same configuration gives 486/486 identical top-25 rankings.
- [x] **The extended set `sop-main-v2`** (requested by the owner on 2026-11-04 after seeing that `sop-main` could not separate the configurations; frozen 2026-11-05):
  - 96 new intents that do not mention document codes. Each intent has a same-language question and a cross-lingual one, with "near-miss" negatives.
  - Harness: `extend_dataset`, `run --allow-draft`, a bootstrap clustered by `intent_id`, counting questions won/lost.
  - Review: drafted by Claude, cross-checked against the corpus by a Claude subagent, approved by the owner on Claude's review results. `test_sha256 = a568bf74…8059`. `sop-main` keeps its hash.
  - Official RQ1/RQ3/RQ5 numbers in §12 of the AUDIT report:
    - cross-lingual: dense beats hybrid by +0.26 [0.16; 0.37] (won 19, lost 0);
    - same language: hybrid beats dense by +0.035, with the CI touching 0;
    - `cross_lingual_bm25_factor` has no effect;
    - Qwen3-0.6B is on par with bge-m3.
  - RQ2 on v2, 1 run: hybrid + rerank reaches 0.940, cross-lingual 0.893; +0.137 over hybrid and +0.067 over dense. Cost: 18.1 s/question on CPU.
  - RQ2b: reranking the top 25 of dense, hybrid 1/1 or hybrid 0.7/0.3 gives the same results (0.940–0.945, differences ≤ 0.014). Dense + rerank is the simplest configuration.
  - The owner decided on the §12 proposals on 2026-11-07, see §6.

## 6. Decision 2026-11-07

The owner set the ticket `done` on the report [AUDIT-eval-rq1-rq3-2026-11-04](../../../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) (`final`). The proposals in §8 and §12 of the report were taken as follows; `services/ai-service/config/models.yaml` is **not changed**.

| Item | Decision |
|---|---|
| Embedding model | Keep `bge-m3`; Qwen3-Embedding-0.6B is an equivalent option, no reason to switch yet |
| `cross_lingual_bm25_factor` | Keep `1.0` |
| `retrieval.thresholds` | Not written from these numbers; recalibrate in V2-10 with a dev set that has more, harder negatives or with signals beyond cosine (rerank score, an LLM-level check) |
| NFR recall@5 ≥ 0.80 | Not lowered |
| Rerank | Not on by default on CPU (15.7 to 18.1 s/question) |

**Moved to V2-10 and V2-18 (not yet decided, not blocking V2-07):**
- The default retrieval mode. `models.yaml` has `hybrid`, but on `sop-main-v2` hybrid loses to dense on cross-lingual questions (+0.26, won 19 lost 0). Without rerank, dense is better overall; with rerank, dense + rerank is the simplest configuration with the same quality as hybrid + rerank. Must be decided together with the latency budget (GPU or not).
- The option of a BM25 branch by question language (off when it differs from the majority language) or question translation: not measured.
- The placeholder `thresholds` (dense 0.45, hybrid 0.45) are below the dev thresholds (0.619 and 0.482), so they block almost no negatives; V2-10 must replace them before enabling the gate.
- The `sop-main-v2` data and `eval/results/` are gitignored; only the freeze hash and the report are in the repo.
