---
id: AUDIT-EVAL-RQ1-RQ3-2026-11-04
title: "V2-07: RQ1/RQ1b/RQ2/RQ3/RQ5 multilingual retrieval on sop-main"
type: audit
status: final
created: 2026-11-04
updated: 2026-11-13
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [eval, ai-service]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-07-run-rq1-rq3-rq5.md
  - docs/architecture/components/ai-service.md
  - docs/research/research-04-experiment-tooling.md
  - eval/datasets/sop-main/README.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. Decimal commas are written as decimal points.

# V2-07: RQ1–RQ3 and RQ5 retrieval numbers

> **Report id:** `AUDIT-EVAL-RQ1-RQ3-2026-11-04` | **Run date:** 2026-11-04 | **Conclusion:** `PASSED_WITH_WARNINGS`. The retrieval numbers are complete; the test set's cross-lingual group has only 5 questions and the RQ3 threshold was chosen on dev's 4 negative questions, so these two conclusions are not firm enough to change configuration. **No threshold or factor was written into the ai-service configuration**; sections 8 and 12 are proposals; the owner settled them on 2026-11-07 as recorded in [V2-07 §6](../execution/initiatives/v2-sopilot-mvp/tickets/V2-07-run-rq1-rq3-rq5.md), still without changing the ai-service configuration.

## 1. Summary

- **RQ1 (test, 70 answerable questions, bge-m3):** hybrid RRF 1/1 reaches `span_recall@5` 0.938 versus dense 0.902 (+0.036, 95% CI [−0.01; +0.09]); `full@5` (every required span in the top 5 chunks) 0.914 versus 0.857 (+0.057, CI [0.00; +0.13]). In the same-language group (65 questions) hybrid clearly beats dense: +0.054 [+0.02; +0.11]. BM25 alone 0.840; the old 0.7/0.3 weights (0.895) do not beat dense.
- **NFR target recall@5 ≥ 0.80:** dense and hybrid both exceed it on the whole test set by `span_recall@5`. The weakest group is Vietnamese questions about Vietnamese documents (dense 0.828, hybrid 0.906) and the `multi_passage` type (`full@5` 0.625 / 0.750).
- **RQ1b (cross-lingual):** hybrid **loses** to dense in the cross-lingual group on both dev (0.50 versus 1.00; 10 questions) and test (0.80 versus 1.00; 5 questions). The ticket's rule picks `cross_lingual_bm25_factor` **0.3** on dev (0.60, one question better), but on test it gives exactly the same result as 1.0. Error analysis (section 4.2) shows the factor does not touch the cause: BM25 promotes **wrong chunks in the same language as the question**, while the factor only lowers chunks in the other language (that is, the right chunks).
- **RQ2 (bge-reranker-v2-m3 rerank on hybrid's pool of 25):** `span_recall@5` 0.957 versus 0.938 (+0.019 [−0.02; +0.06], not clear), but `mrr_span` 0.943 versus 0.816 (+0.127 [+0.06; +0.19]) and the cross-lingual group 5/5 (dev 0.90 versus 0.50). The cost: p50 **17.7 s per question** on this CPU (versus 0.15 s), peak RAM 5.1 GB while holding both models. The rerank score separates negative questions far better than cosine (section 6).
- **RQ3:** the cosine gate separates answerable and negative questions poorly (mean top `dense_score` 0.697 versus 0.597 on test). The threshold chosen on dev by the predefined rule (min FR+FA) is 0.619 for dense; measured on test: false refusal 0.086, false answer 0.455 (5/11 negatives get through). The `rerank_score` gate separates well (0.959 versus 0.288; on test a threshold exists with FR 0.029 / FA 0), but the threshold chosen on dev (0.269) still gives FA 0.455 because dev's 4 negatives are much easier than test's. Dev has too few negatives to choose a threshold.
- **RQ5:** bge-m3 is the best in both quality and speed on this machine. Qwen3-Embedding-0.6B is worse (dense 0.852) and about 30% slower; multilingual-e5-large-instruct is worse (0.857) and about 6 times slower (corpus embedding 33 minutes versus 4).
- **Reproducibility:** rerunning the same configuration in a separate process gives 486/486 identical top-25 rankings; the 3 latency passes within each run also give identical rankings.

## 2. Run conditions

| Item | Value |
|---|---|
| Machine | AMD Ryzen 7 8845HS (8 cores / 16 threads), 31.3 GB RAM, Windows 11 Pro 10.0.26300, CPU only (torch 2.14.1+cpu, 8 torch threads) |
| Libraries | Python 3.12.10, sentence-transformers 6.1.0, transformers 5.20.1 |
| Data | `eval/datasets/sop-main`, `corpus_version=sop-main-2026-11-04-v2`, **frozen**, `test_sha256=f80c2e5d22a9d2f5454953135b61875630d55567ab9ec0f07e2feb8862102aaf`; 23 documents (13 VI, 10 EN), 218 spans. The `--require-reviewed` validator runs at the start of every run (green) |
| Split | dev 24 questions (20 answerable, 4 negative; 10 cross-lingual), test 81 questions (70 answerable, 11 negative; 5 cross-lingual: 3 EN→VI, 2 VI→EN) |
| Chunks | `chunking: docproc` (`sopilot_ai.docproc`, `normalizer_version=2`, corpus built with docproc commit `26d1ed1`, the docproc code at HEAD unchanged since that commit); target 384 / max 512 tokens by the tokenizer of the model being measured; `title` = `doc_id`; `index_text` (title › section + content) is embedded and BM25-indexed. bge-m3: 575 chunks, `chunks_sha256=cfe9d64b…c7895e6` |
| BM25 | The final tokenizer of TECH-V2-ai-service §6.3 (`nfc-lower-w+-uni+bi+fold~-v2`): unigrams + bigrams, diacritic-free `~` terms, `lexical_len` counts only the original terms; k1 = 1.5, b = 0.75 |
| Hybrid | RRF `rrf_k = 60`, 50 candidates per branch, pool 25. Gate: the top candidate's `dense_score` (cosine), always present because the in-memory index computes cosine for every chunk; `bm25` has no gate; with rerank the gate is `rerank_score` (sigmoid) |
| Models (HF revision) | bge-m3 `5617a9f6…`, bge-reranker-v2-m3 `953dc6f6…`, Qwen3-Embedding-0.6B `97b0c614…`, multilingual-e5-large-instruct `274baa43…` (details in `eval/configs/`) |
| Harness code | The runs ran on a working tree based on commit `f706308` plus **uncommitted** V2-07 changes (`run.json` records `dirty: true`). Record the hash in the ticket when committed |

### Metrics

- `span_recall@k`: for each OR evidence set, the share of required spans covered by the top-k chunks (a span counts as present when the chunks cover ≥ 50% of its characters); the best set is taken. `full@k` = 1 when one set is fully covered; `any@k` = 1 when at least one span is; `mrr_span` by the first chunk touching a gold span. `hit@5` is the old document/page-level proxy.
- CIs are 95% bootstrap (resampling questions, 2000 times, seed 0). Comparisons between configurations are paired differences on the same questions.
- Latency: retrieval time for one question (question embedding + in-memory scoring + rerank if any), without the LLM; p50/p95 of each pass, averaged over 3 passes, with the standard deviation between passes.

### Feasibility smoke (50 docproc chunks, 3 passes, one process per model)

| Model | Load | ms/chunk (warm, sd) | Peak RAM | Decision |
|---|---|---|---|---|
| bge-m3 | 8.9 s | 445 (0.1) | 2.3 GB | Into the matrix (RQ1–RQ3, RQ5) |
| bge-reranker-v2-m3 | 10.7 s | 644 per pair (4.6) → ~16 s/question with pool 25 | 3.5 GB | Into the matrix, but run with its own configuration file (`rq2-rerank-bge-m3.yaml`), both dev and test |
| Qwen3-Embedding-0.6B | 9.0 s | 582 (2.6) | 2.8 GB | Into RQ5 |
| multilingual-e5-large-instruct | 10.4 s | 2,669 (9.2) | 2.1 GB | Into RQ5 despite being slow (~26–33 minutes for the corpus). 6 times slower than bge-m3 despite the same XLM-R large architecture: **cause unknown, not investigated** |

Command: `python -m sopilot_eval.smoke_models --dataset datasets/sop-main --kind embed|rerank --model … --revision … --out results/smoke-models/<model>.json`.

## 3. RQ1: dense, BM25, hybrid (bge-m3)

Runs: dev `eval/results/20261104-145508-23cb859c/`, test `eval/results/20261104-150006-3e20dc7c/` (analysis: `…/analysis/analysis.md`), rerun to check reproducibility `eval/results/20261104-150255-1f9773d8/`.

### 3.1 Test, by language and cross-lingual (`span_recall@5` [95% CI])

| Configuration | All (70) | VI→VI (32) | EN→EN (33) | Cross-lingual (5) | `full@5` all | `mrr_span` | p50 / p95 ms (sd) |
|---|---|---|---|---|---|---|---|
| dense | 0.902 [0.84; 0.96] | 0.828 [0.70; 0.94] | 0.960 [0.91; 1.00] | 1.000 | 0.857 | 0.783 | 112 / 133 (0.9 / 1.7) |
| bm25 | 0.840 [0.76; 0.92] | 0.797 [0.67; 0.92] | 0.980 [0.94; 1.00] | 0.200 [0.00; 0.60] | 0.814 | 0.772 | 3 / 5 (0.2 / 0.5) |
| hybrid 1/1 | **0.938** [0.89; 0.99] | **0.906** [0.81; 0.98] | **0.990** [0.97; 1.00] | 0.800 [0.40; 1.00] | **0.914** | **0.816** | 116 / 142 (0.6 / 0.6) |
| hybrid 0.7/0.3 | 0.895 [0.83; 0.95] | 0.828 [0.70; 0.94] | 0.975 [0.93; 1.00] | 0.800 [0.40; 1.00] | 0.857 | 0.781 | 122 / 144 (4.5 / 5.6) |

Cross-lingual by direction (test): dense 3/3 EN→VI and 2/2 VI→EN; hybrid 2/3 EN→VI and 2/2 VI→EN; bm25 1/3 and 0/2.

Paired differences against dense (test, `span_recall@5` / `full@5`):

| Configuration | All (70) | Same language (65) | Cross-lingual (5) |
|---|---|---|---|
| bm25 | −0.062 [−0.14; +0.01] / −0.043 | −0.005 [−0.07; +0.06] / +0.015 | −0.800 [−1.00; −0.40] |
| hybrid 1/1 | +0.036 [−0.01; +0.09] / +0.057 [0.00; +0.13] | +0.054 [+0.02; +0.11] / +0.077 [+0.03; +0.15] | −0.200 [−0.60; 0.00] |
| hybrid 0.7/0.3 | −0.007 [−0.04; +0.02] / 0.000 | +0.008 [0.00; +0.02] / +0.015 | −0.200 [−0.60; 0.00] |

### 3.2 Dev (24 questions, 20 answerable; the pilot's 4 documents)

| Configuration | All | Same language (10) | Cross-lingual (10) |
|---|---|---|---|
| dense | 1.000 | 1.000 | 1.000 |
| bm25 | 0.525 | 0.950 | 0.100 |
| hybrid 1/1 | 0.750 | 1.000 | 0.500 |
| hybrid 0.7/0.3 | 0.850 | 1.000 | 0.700 |

Dev is small with a high cross-lingual share (10/20, versus 5/70 in test), so the dense/hybrid order on dev is the reverse of test. Dev is only used to choose parameters (RQ1b, RQ3), not for conclusions.

### 3.3 Test by `query_types` (`span_recall@5` / `full@5`)

| Type (n) | dense | bm25 | hybrid 1/1 | hybrid 0.7/0.3 |
|---|---|---|---|---|
| comparison (10) | 0.850 / 0.800 | 0.750 / 0.700 | 0.900 / 0.900 | 0.850 / 0.800 |
| condition_exception (27) | 0.907 / 0.889 | 0.870 / 0.852 | 1.000 / 1.000 | 0.907 / 0.889 |
| fact (24) | 0.917 / 0.875 | 0.812 / 0.792 | 0.896 / 0.875 | 0.875 / 0.833 |
| multi_passage (16) | 0.792 / 0.625 | 0.708 / 0.625 | 0.854 / 0.750 | 0.823 / 0.688 |
| number_deadline (26) | 0.910 / 0.846 | 0.859 / 0.808 | 0.929 / 0.885 | 0.910 / 0.846 |
| procedure (22) | 0.932 / 0.909 | 0.909 / 0.909 | 1.000 / 1.000 | 0.955 / 0.955 |
| responsibility (20) | 0.875 / 0.850 | 0.700 / 0.650 | 0.875 / 0.850 | 0.825 / 0.800 |

A question can have several types, so the total n exceeds 70. `multi_passage` is the hardest type for every configuration: a single chunk does not contain all the evidence, which is exactly what §6.4a context assembly (V2-10) targets.

## 4. RQ1b: hybrid in the cross-lingual group

### 4.1 Numbers

Hybrid loses to dense on cross-lingual, so per the ticket `cross_lingual_bm25_factor` ∈ {0.3; 0} was also run.

| Configuration | Dev cross (10) | Dev all (20) | Test cross (5) | Test all (70) |
|---|---|---|---|---|
| hybrid, factor 1.0 | 0.500 | 0.750 | 0.800 | 0.938 |
| hybrid, factor 0.3 | **0.600** | 0.800 | 0.800 | 0.938 |
| hybrid, factor 0 | 0.500 | 0.750 | 0.800 (EN→VI 3/3, VI→EN 1/2) | 0.938 |
| dense (reference) | 1.000 | 1.000 | 1.000 | 0.902 |

Selection rule (predefined in `analyze_v2_07.py`): highest dev cross `span_recall@5`, ties broken by dev all. Result: **0.3**, beating 1.0 by exactly **1 question** on dev; no different from 1.0 on test. Same-language results are unchanged (the factor only touches chunks in a language other than the question's).

### 4.2 Why the factor has no effect

The five dev cross-lingual questions that hybrid with factor 0 still misses are all Vietnamese questions about English GitLab pages. Dense ranks `gitlab-buddies`/`gitlab-meetings` in the top 3; hybrid puts `tb-qt05`, `tb-qt03`, `vn-qd1308`, `nb-qt03` (Vietnamese documents, wrong) at the top. BM25 for a Vietnamese question can only match Vietnamese documents, and those chunks are **in the same language as the question**, so the factor does not lower them; factor 0 even erases the small BM25 contribution of the right chunk. The §6.4 design assumed the noise is in other-language chunks, while the data shows the noise is in same-language chunks of the wrong document.

Options to consider (not measured, owner decides): lower the overall BM25 weight (0.7/0.3 lifts dev cross to 0.70 but loses the same-language gain on test); add the BM25 branch only when a candidate's BM25 score is high enough; or keep it and accept, since cross-lingual is a minority in real use. All three need more cross-lingual questions (test has only 5) to conclude.

## 5. RQ2: rerank

Runs: dev `eval/results/20261104-160249-6f8cf9d6/`, test `eval/results/20261104-162508-69ca2844/`. The same pool of 25 from hybrid 1/1; rerank rescores the 25 candidates using `index_text`, `max_length=512`. Run on the whole dev and test sets (no subset needed), 3 passes.

| Test (70) | `span_recall@5` | `full@5` | `span_recall@10` | `full@10` | `mrr_span` | Cross (5) | VI→VI (32) | EN→EN (33) | p50 / p95 ms (sd) |
|---|---|---|---|---|---|---|---|---|---|
| hybrid (rerank off) | 0.938 | 0.914 | 0.971 | 0.957 | 0.816 | 0.800 | 0.906 | 0.990 | 151 / 182 (1.2 / 1.0) |
| hybrid + rerank | **0.957** | **0.929** | **0.979** | **0.971** | **0.943** | **1.000** | **0.922** | 0.985 | 17,697 / 20,082 (78 / 129) |

Paired difference rerank − hybrid (test): `span_recall@5` +0.019 [−0.02; +0.06]; `full@5` +0.014 [−0.04; +0.07]; `mrr_span` +0.127 [+0.06; +0.19]. Same language (65): `mrr_span` +0.096 [+0.03; +0.16], recall unchanged. Cross-lingual (5): +0.200 [0.00; +0.60]. Dev: 0.750 → 0.950 (cross 0.50 → 0.90).

By `query_types` (test, `span_recall@5` / `full@5`): comparison 0.850 / 0.700; condition_exception 1.000 / 1.000; fact 0.917 / 0.875; multi_passage 0.875 / 0.750; number_deadline 0.962 / 0.923; procedure 1.000 / 1.000; responsibility 0.900 / 0.850.

Reading: rerank rarely brings more evidence into the top 5 (hybrid's pool of 25 already contains the evidence for 97% of questions); it mostly **moves it up to rank 1** (`mrr_span`) and fixes exactly hybrid's cross-lingual weakness. A latency of 17.7 s per question on a laptop CPU is unusable for chat; rerank is only feasible on a GPU, on a smaller pool or with a smaller model (not measured).

## 6. RQ3: threshold gate (false refusal / false answer)

Predefined selection rule: on dev, choose the smallest threshold minimizing `false_refusal + false_answer` (equal weights); apply it unchanged to test. The "best threshold on test" is only a reference, not used for selection. This is a retrieval-level proxy (refuse when the gate score < threshold), not an LLM answer-level refusal.

| Configuration (gate score) | Dev threshold | Dev FR / FA | **Test FR / FA** | Best threshold on test (FR / FA) | Test mean `gate`: answerable / negative |
|---|---|---|---|---|---|
| dense (cosine) | 0.6192 | 0.200 / 0.000 | **0.086 / 0.455** | 0.6669 (0.257 / 0.000) | 0.697 / 0.597 |
| hybrid 1/1 (top candidate's cosine) | 0.4815 | 0.000 / 0.250 | **0.014 / 0.909** | 0.6605 (0.314 / 0.000) | 0.684 / 0.584 |
| hybrid 0.7/0.3 | 0.4862 | 0.000 / 0.250 | 0.014 / 0.909 | 0.6621 (0.271 / 0.000) | 0.689 / 0.590 |
| hybrid factor 0.3 | 0.5768 | 0.350 / 0.000 | 0.043 / 0.636 | 0.6605 (0.300 / 0.000) | 0.683 / 0.584 |
| hybrid + rerank (`rerank_score` sigmoid) | 0.2686 | 0.050 / 0.000 | **0.014 / 0.455** | 0.7087 (0.029 / 0.000) | 0.959 / 0.288 |
| bm25 | no gate | | | | |

Observations:
- Dev has 4 negatives, test 11. One negative on dev is 25 percentage points of FA, so the threshold jumps with each question: for hybrid, the rule accepts letting 1/4 negatives through to avoid any false refusal, and on test that lets 10/11 through.
- Even the best threshold on test (cosine ≈ 0.66–0.67) must falsely refuse 26–31% of answerable questions to block every negative. bge-m3's cosine on this corpus does not separate the two groups clearly enough for a single threshold to both refuse little and block negatives.
- With rerank, dev's 4 negatives score 0.00–0.10 while test's 11 negatives spread from 0.01 to 0.68; the dev threshold sits just above dev's highest negative, so it lets 5/11 test negatives through. Choosing on test (for reference only), 0.71 gives FR 0.029 / FA 0: the rerank gate can separate, but the current dev is not enough to choose the threshold.
- sop-main's negatives were written to be close to the corpus topics (see `negative-audit.draft.jsonl`), so this is a hard case; clearly off-topic questions would have much lower cosine.

## 7. RQ5: comparing embedding models

Runs: dev `eval/results/20261104-151314-80d982a6/`, test `eval/results/20261104-155353-f9df1f69/`. The same target/max 384/512, counted by each model's tokenizer (Qwen3 gives 561 chunks, the two XLM-R models 575). Questions have the instruction prefix per the model card (Qwen3, e5); documents do not.

| Model | Mode | Test all (70) | VI→VI (32) | EN→EN (33) | Cross (5) | `full@5` | `mrr_span` | Dev all / cross | Corpus embedding | Retrieval p50 ms (sd) |
|---|---|---|---|---|---|---|---|---|---|---|
| bge-m3 | dense | **0.902** | 0.828 | **0.960** | **1.000** | **0.857** | **0.783** | 1.000 / 1.000 | 239 s (575 chunks) | 139 (0.6) |
| bge-m3 | hybrid | **0.938** | **0.906** | **0.990** | 0.800 | **0.914** | **0.816** | 0.750 / 0.500 | | 146 (2.5) |
| Qwen3-Embedding-0.6B | dense | 0.852 | 0.797 | 0.914 | 0.800 | 0.814 | 0.688 | 0.850 / 0.850 | 278 s (561) | 142 (2.4) |
| Qwen3-Embedding-0.6B | hybrid | 0.890 | 0.859 | 0.965 | 0.600 | 0.857 | 0.771 | 0.625 / 0.250 | | 145 (0.6) |
| multilingual-e5-large-instruct | dense | 0.857 | 0.812 | 0.939 | 0.600 | 0.843 | 0.712 | 0.900 / 0.800 | 1,997 s (575) | 696 (10.0) |
| multilingual-e5-large-instruct | hybrid | 0.902 | 0.891 | 0.960 | 0.600 | 0.871 | 0.770 | 0.600 / 0.200 | | 699 (3.2) |

- Corpus embedding time is measured on each model's first run (empty cache); bge-m3's comes from the RQ1 dev run because the RQ5 run reused its cache. The RQ5 process holds all three models, peak RAM 5.0 GB; bge-m3's latency here (139 ms) is higher than in the RQ1 run (112 ms) because of the shared process, so compare latency only between models within this table.
- RQ3 per model (dense cosine gate, dev threshold → test FR/FA): Qwen3 0.614 → 0.057 / 0.545; e5 0.860 → 0.029 / 0.727. For every model, negative cosine sits close to answerable cosine (e5: 0.886 versus 0.911).
- RQ5 conclusion: no reason to move away from bge-m3 on this data.

## 8. Proposals for the owner (settled 2026-11-07, not applied to configuration)

> This table is based on `sop-main`. Its conclusion on the default mode is superseded by §12 (`sop-main-v2`): dense beats hybrid on cross-lingual questions.

| Item | Proposal | Evidence / confidence |
|---|---|---|
| Default retrieval mode | Keep hybrid RRF 1/1 on bge-m3 | Beats dense on same-language questions, CI excluding 0 (65 questions) |
| The 0.7/0.3 weights | Not the default | Does not beat dense on test |
| `retrieval.cross_lingual_bm25_factor` | The ticket's rule picks 0.3 on dev. Proposed: **keep 1.0** until there are more cross-lingual questions: 0.3 is only one dev question better, test shows no difference, and the mechanism (section 4.2) shows the factor does not target the cause | Weak: 10 dev questions, 5 test questions |
| `retrieval.thresholds` | Thresholds by the dev rule: dense 0.619, hybrid 0.482, hybrid_rerank 0.269. Proposed: **do not write** them into ai-service yet: test FA 0.455 / 0.909 / 0.455. Add harder negatives to dev (currently 4, easier than test) and choose again, or accept that the cosine gate only blocks clearly off-topic questions and let the LLM refuse by itself (D2) | Weak |
| Rerank | Not on by default on CPU (17.7 s/question). Worth remeasuring with a GPU or a lighter rerank model: `mrr_span` +0.13, fixes cross-lingual, and the rerank score is the best gate for separating negatives | Medium (recall@5 not clearly different; MRR clearly different) |
| Embedding model | Keep bge-m3 | Equal to or better than the other two in every test group; fastest embedding |
| NFR target recall@5 ≥ 0.80 | No need to lower it: dense 0.902, hybrid 0.938 on test | Medium |

Note: while V2-07 was running, a V2-09 session (now committed in `30f530b`, not part of this report) added `services/ai-service/config/models.yaml` with placeholder `retrieval.thresholds` (dense 0.45, hybrid 0.45, hybrid_rerank 0.30) and `cross_lingual_bm25_factor: 1.0`, together with `sopilot_ai.retrieval.lexical`. This report **does not edit** that file. That module's tokenizer gives the same terms as the harness on 105 questions and 3 sample documents (checked 2026-11-04). Note the placeholder 0.45 is below the dev thresholds for dense (0.619) and hybrid (0.482), so it would let almost every test negative through.

## 9. Limits and what was not checked

- **Small scale:** 23 documents, 575 chunks; test has 70 answerable questions, 11 negatives, **5 cross-lingual questions**. The CI of the cross-lingual group spans almost the whole [0; 1] range.
- **Dev differs in distribution from test:** dev uses the 4 pilot documents, half the questions are cross-lingual; thresholds and factors chosen on dev may not transfer to test (as seen in RQ3).
- **Retrieval only:** V2-10 is not finished; there are no LLM answers, faithfulness or citations yet. RQ3 is a retrieval proxy.
- **Simple BM25 tokenization:** `\w+` + bigrams + diacritic-free terms; no Vietnamese word tokenizer or English stemming.
- **Document titles are `doc_id`** (for example `nb-qt02`) because the manifest has no user-given titles; the real service uses the title from upload, so the service's `index_text` will differ.
- **Question language** comes from the dataset labels, not the service's language detector (§7.1).
- **Chunks close to 512 tokens** may lose their last 2 tokens when the model adds special tokens (the docproc tokenizer counts without special tokens).
- **Chunks are not built from the original PDFs** but from the cached Docling extraction (`results/extraction-clean/structured`) and 2 Markdown pages; every document was checked to re-render byte-for-byte identical to the frozen corpus before chunking.
- Rerank measured only one model and pool 25; smaller pools or lighter rerank models were not measured.
- **Not checked:** e5's abnormal slowness (not investigated); RQ4 (access filtering latency on Postgres) out of scope; laptop latency may be affected by background tasks; no GPU.
- **Uncommitted code:** the runs ran on a working tree (`dirty: true`).

## 10. Reproduction

```powershell
cd eval
uv sync --extra local --extra dev          # includes services/ai-service (path dependency)
$env:HF_HUB_OFFLINE = "1"
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --split dev --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --split test --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq5-models.yaml --split dev|test --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq2-rerank-bge-m3.yaml --split dev|test --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.analyze_v2_07 --dev results/<dev> --test results/<test> --out results/<test>/analysis
```

`eval/results/` and `eval/datasets/` are gitignored: the run directories and datasets exist only on the owner's machine.

## 11. Harness tests

- `.venv/Scripts/python.exe -m pytest -q` in `eval/`: 90 passed (2026-11-04). The V2-07 tests in `tests/test_v2_07_retrieval.py`: the `~` tokenizer, the `dense_score` gate for BM25-only candidates, the cross-lingual factor, BM25 without a gate, span metrics, the threshold selection rule.

## 12. The extended set `sop-main-v2` (frozen 2026-11-05)

Reason: on `sop-main`, 57–65/70 test questions reach span_recall@5 = 1.0 in every configuration; 36/81 questions name a document code; there are only 5 cross-lingual questions and 4 negatives on dev. The set is not enough to distinguish configurations. `sop-main` is kept unchanged (hash `f80c2e5d…aaf`).

`eval/datasets/sop-main-v2` contains every v1 question plus 96 new intents (`subset=v2`), see `eval/datasets/sop-main-v2/README.md`:
- New questions do not name document codes; the word overlap with the quotes drops from 0.52 (v1) to 0.40.
- Each intent has two questions: one in the same language, one cross-lingual.
- Test has 200 answerable questions (70 cross-lingual) and 39 negatives; dev has 40 answerable questions and 14 negatives.
- CIs use a bootstrap clustered by `intent_id`.

**Review process (recorded exactly as done):**
- Claude drafted 188 new questions.
- A Claude subagent (Opus 5.5, clean context) reviewed each question against the corpus:
  - 168 passed;
  - 16 had clear errors and were fixed, mostly gold spans shorter than the answer;
  - 2 awaited the owner's decision;
  - 2 were proposed for removal.
- The owner decided two points:
  - Test may cite dev documents when the content is verbatim identical (nb-qt03/tb-qt03). Recorded in the README, section 7.
  - Replace `v2d-buddy-pick`, which duplicated a v1 intent, with `v2d-buddy-mentorship`.
- The owner **reviewed on the basis of Claude's review results**, without personally checking each question against the corpus.
  - Each record in `review.jsonl` has `reviewer_id=owner:tiên`, `drafted_by=Claude`, `ai_reviewer=claude-opus-5-5` and `review_basis=claude_review`.
  - Review details are in `REVIEW-claude.md` and `review-verdicts.claude.jsonl`.
- Freeze: `test_sha256 = a568bf74903ede0e153bb16883ba24cc4ca76c9ad30b5410b2b71e830df18059`.

**Official numbers** (RQ1/RQ3 runs: `results/20261105-115341-b569765f` dev, `…115557-998681b7` test; RQ5: `…120446-accf98a6` dev, `…121034-50ef4f1c` test; analysis in `<test>/analysis/`; `--repeats 3`; `dataset_info.reviewed=true`). The table is span_recall@5 on test [95% CI]:

| configuration | all (200) | same language (130) | cross-lingual (70) |
|---|---|---|---|
| dense bge-m3 | **0.873** [0.82; 0.92] | 0.886 | **0.850** [0.76; 0.93] |
| bm25 | 0.602 | 0.879 | 0.086 |
| hybrid 1/1 | 0.803 | **0.921** | 0.586 [0.47; 0.70] |
| hybrid 0.7/0.3 | 0.823 | 0.897 | 0.686 |
| hybrid xl0.3 / xl0 | 0.798 / 0.801 | 0.921 | 0.571 / 0.579 |
| dense Qwen3-0.6B (RQ5) | 0.868 | 0.871 | **0.864** |
| hybrid Qwen3-0.6B | 0.769 | 0.906 | 0.514 |
| dense e5-large-instruct | 0.695 | 0.862 | 0.386 |
| hybrid e5-large-instruct | 0.663 | 0.905 | 0.214 |

Paired differences (span_recall@5, questions won/lost):
- **Cross-lingual: dense beats hybrid by +0.264 [0.16; 0.37], 19 won, 0 lost.** Hybrid 0.7/0.3 limits the damage (+0.100 over hybrid 1/1, 7 won, 0 lost) but still loses to dense.
- **Same language: hybrid beats dense by +0.035 [−0.00; +0.08], 8 won, 2 lost.** A trend in hybrid's favour, but the CI touches 0. On mrr_span the difference is +0.051 [+0.01; +0.09].
- Overall: dense beats hybrid by +0.070 [+0.02; +0.12].
- `cross_lingual_bm25_factor` has no effect.
  - xl0.3 versus hybrid: 0 won, 1 lost. xl0: 3 won, 3 lost.
  - RQ1b on dev chooses `hybrid` (factor 1.0).
  - Same mechanism as §4: BM25 promotes chunks *in the same language as the question* but from the wrong document, while the factor only lowers other-language chunks.
- RQ5:
  - Qwen3-0.6B dense is on a par with bge-m3 dense, both overall (0.868 versus 0.873) and cross-lingual (0.864 versus 0.850). The CIs overlap.
  - e5-large-instruct is clearly weak on cross-lingual (0.386).
  - For every model, hybrid drags cross-lingual down.

RQ3 (threshold chosen on dev, measured on test, 200 answerable / 39 negatives):

| configuration | dev threshold | test FR | test FA | test oracle t (FR/FA) |
|---|---|---|---|---|
| dense bge-m3 | 0.6059 | 0.245 | 0.538 | 0.6430 (0.430/0.103) |
| hybrid bge-m3 | 0.6059 | 0.385 | 0.359 | 0.6359 (0.500/0.128) |
| dense Qwen3-0.6B | 0.6119 | 0.250 | 0.538 | 0.6568 (0.390/0.308) |
| dense e5 | 0.8593 | 0.280 | 0.615 | 0.8873 (0.435/0.256) |

The top-1 cosine gate separates answerable questions poorly from "near-miss" negatives. Even the optimal threshold measured on test itself falsely refuses 39–50% of answerable questions. A single cosine threshold should not be relied on to refuse answers.

**RQ2: rerank on the v2 set.**
- Runs: `results/20261105-145227-2f4fd6e7` (dev) and `…173421-90a5e580` (test); analysis in `<test>/analysis/`.
- `--repeats 1`. Latency was already measured over 3 passes on `sop-main` (§5).
- Rerank with bge-reranker-v2-m3 on hybrid's pool of 25 candidates.

| configuration (test) | all (200) | same language (130) | cross-lingual (70) | mrr_span all |
|---|---|---|---|---|
| hybrid | 0.803 | 0.921 | 0.586 | 0.650 |
| **hybrid + rerank** | **0.940** [0.91; 0.97] | **0.965** | **0.893** [0.81; 0.96] | **0.894** |
| dense (RQ1, for comparison) | 0.873 | 0.886 | 0.850 | 0.740 |

span_recall@5 differences:
- **Rerank versus hybrid:** +0.137 [+0.09; +0.19] (31 won, 2 lost).
  - Cross-lingual: +0.307 [+0.21; +0.41] (22 won, 0 lost).
  - Same language: +0.045 [+0.01; +0.08] (9 won, 2 lost).
- **Rerank versus dense** (paired with the RQ1 run, bootstrap by question):
  - All: +0.067 [+0.02; +0.11] (20 won, 4 lost).
  - Same language: +0.079 [+0.04; +0.13].
  - Cross-lingual: +0.043 [−0.04; +0.13], not clear.
- **Meaning:** rerank repairs almost all the cross-lingual damage BM25 does to hybrid. This is the best configuration in every group.
- **Dev:** 0.975 versus hybrid's 0.675.
- **The cost:** p50 **18.1 s/question**, p95 21.5 s, on this CPU. Without rerank, 0.15 s. Peak RAM 5.1 GB.
- **Run time:** the test pass ran for 72 minutes uninterrupted because the machine was kept awake. The two earlier stops were caused by the machine sleeping (Modern Standby/sleep, see the System Event Log), not by a lack of RAM.

**RQ2b: rerank on which candidate source?** (owner asked 2026-11-05)
- Runs: `results/20261105-211945-9d7eabc7` (dev) and `…214840-ad128122` (test).
- Config `configs/rq2b-rerank-pools.yaml`, run with `--repeats 1`.

| rerank the top 25 of (test) | all (200) | same language (130) | cross-lingual (70) | mrr_span all |
|---|---|---|---|---|
| dense | 0.940 | 0.958 | 0.907 | 0.895 |
| hybrid 1/1 (RQ2) | 0.940 | 0.965 | 0.893 | 0.894 |
| hybrid 0.7/0.3 | 0.945 | 0.965 | 0.907 | 0.898 |

- **The three candidate sources give the same results.** Every span_recall@5 difference between them is within ±0.014, the CIs contain 0, and the differences are only 1–2 questions.
  - Before running, the ceiling was estimated: the share of questions with all the evidence in the top 25 is 0.960 for dense, 0.965 for hybrid 1/1 and 0.975 for hybrid 0.7/0.3.
  - Since the ceilings are almost equal, the reranker gets close to the ceiling whatever the source.
- **Dense + rerank versus dense:** +0.067 [+0.03; +0.11] (19 won, 3 lost); mrr_span +0.155.
- **Dev:** all three rerank configurations reach 1.000. Dev cannot distinguish them.
- **Latency:** p50 15.7 s/question for both dense + rerank and hybrid 0.7/0.3 + rerank. The hybrid + rerank pass in RQ2 measured 18.1 s, but that was a different run, so it cannot be compared directly. Peak RAM 5.1 GB.
- **RQ3:** dense + rerank and hybrid 0.7/0.3 + rerank give the same dev threshold and the same test oracle as hybrid + rerank.
- **Consequences:**
  - With rerank, the BM25 branch makes no measurable contribution on this set.
  - **Dense + rerank is the simplest configuration that still reaches the best quality**, with no BM25 index or fusion needed.
  - Without rerank, BM25 still helps same-language questions (§12 RQ1).

**RQ3 with the rerank score gate (sigmoid):**
- The threshold chosen on dev is 0.1076. Measured on test: FR 0.140 / FA 0.564.
- The test oracle: t = 0.7059 gives FR 0.300 / FA 0.051. Hybrid's cosine gate gives FR 0.500 / FA 0.128.
- The rerank score separates answerable questions from negatives better than cosine, but the threshold chosen on dev transfers very poorly to test: FA goes from 0.143 to 0.564. The reason is that dev has only 14 negatives and 4 documents.
- This threshold is not written into `retrieval.thresholds`.

**Limits of the v2 set itself:**
- Dev is too easy for dense: bge-m3 dense reaches 1.000 on all 40 dev questions.
  - Cause: dev has only 4 documents.
  - Consequence: every "on dev" choice in RQ1b and RQ3 has low resolution. RQ3 in particular diverges clearly between dev and test: dense's dev FA is 0.071, its test FA 0.538.
- The questions are still drafted by Claude and the owner has not independently checked them against the corpus.
- The corpus has only 23 documents.

Additional proposals for §8 (owner settled 2026-11-07: the configuration choices move to V2-10/V2-18, not applied here):
1. **Default to dense for cross-lingual questions.** Two options:
   - (a) Detect the question's language; if it differs from the workspace's majority language, turn off the BM25 branch. For same-language questions keep hybrid, since hybrid tends to beat dense.
   - (b) Translate the question before running BM25.
   - Both need their own measurement round on `sop-main-v2`.
2. **If one fixed configuration must be chosen:**
   - With rerank: dense + rerank (or hybrid + rerank, same quality) is best in every group, but 16–18 s/question on CPU. Only feasible with a GPU or when the latency is accepted. Dense + rerank is simpler as it needs no BM25.
   - Without rerank: dense bge-m3 is best overall. Among hybrid configurations, 0.7/0.3 does less harm than 1/1. Do not set `cross_lingual_bm25_factor` to anything other than 1.0.
3. **Qwen3-Embedding-0.6B is an equivalent alternative.** No evidence yet to switch models.
4. **RQ3:** do not write `retrieval.thresholds` from these numbers yet. A signal beyond cosine is needed (the RQ2 rerank sigmoid or verification at the LLM layer), and a harder dev before choosing a threshold.

Not done:
- Measuring proposals 1(a) and 1(b).
- The preview runs in `results/v2-preview/` have been superseded and are no longer cited.

`eval/` pytest after the changes: 95 passed (added `tests/test_extend_dataset.py`).
