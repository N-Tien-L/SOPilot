---
id: RESEARCH-03-methods-and-models
title: "Workstream 03: methods, models and the minimal experiment matrix"
status: final
type: research
scope: research
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
refs:
  - docs/README.md
  - docs/research/research-01-scope-and-rqs.md
  - docs/research/audit-retrieval-stack-research-2026-10-18.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. This is the method design of 2026-10-19; the runs actually done are in AUDIT-eval-rq1-rq3-2026-11-04. `AGENTS.md` and `.agent/` paths are as they were at the time.

# Research methods and model choice

## 1. Method decisions and handover limits

The research shortlist is settled as **two dense embeddings, `BAAI/bge-m3` and `Qwen/Qwen3-Embedding-0.6B`; one reranker, `BAAI/bge-reranker-v2-m3`**. BM25 is an independent lexical branch. Run five retrieval configurations on the whole set; rerank and generate outputs only on a fixed, human-reviewed subset. RQ3 reuses the outputs of the rerank pipeline and does not call the generator again per threshold.

The scope settled by the owner is inherited from workstream 01 and the current request: the original EN corpus, EN/VI queries, two directions EN→EN and VI→EN; no corpus translation. RQ1–3 are the core; RQ5 starts with two embeddings; RQ4 is outside the core. RQ2–3 need real, human-reviewed outputs. 32 GB total RAM, CPU without a GPU; one fixed free API generator, prioritizing quick completion.

This is a design to lock before test, **with no experimental results or winning model yet**. `final` means the method handover is complete; it does not change the status of the PRD/ADR/PLAN/tickets or accept the system. It does not wait for workstreams 02/04: missing inputs are recorded as a handover contract in §10. Data scale, generator quota and the specific CPU have not been verified.

Git was checked before reading: branch `fix/auth-google-roster-admission`, with many existing staged/unstaged/untracked changes, including `eval/` and the input reports. The workstream 03 file did not exist at check time; there was no old content to overwrite. This session only created this file; it did not read `.env`, install/download models, run benchmarks, call keyed APIs, or edit code or progress docs.

## 2. The harness on disk: real capabilities and gaps

The observations below come from reading code on 19/10/2026, not from runs. Paths are from the repo root.

| Component | What really exists | Consequence / what workstream 04 must finish |
|---|---|---|
| `eval/configs/rq1-rq3-bge-m3.yaml` | Dense/BM25/hybrid, hybrid with 0.7/0.3 weights, hybrid-rerank; `k=5`, chunks `800/100`; revisions not pinned | Do not use the YAML as is for the final matrix. Drop the legacy-weight condition from the core; add Qwen dense/hybrid and a locked manifest |
| `embedders.py` | SentenceTransformer, L2 normalization, dot product in the index; a configurable query prefix; every model capped at 512 tokens | A local dense path exists, but Qwen's pooling/instruction/tokenizer/runtime are not proven correct. `build_embedder` does not pass the configured batch; no truncation log |
| Cache | Corpus cache by model name/revision and text hash; queries not cached; the name does not contain the full preprocessing/runtime | Needs a full fingerprint and a separate query cache; do not reuse caches across different pooling/token limits/dtypes |
| `retrievers.py` | Exact dense scan in RAM; hand-written BM25 (`k1=1.5,b=0.75`), NFC/lowercase/unigrams+bigrams, query terms taken unique | A specific BM25 variant, not a generic default BM25. No stemming, query translation or learned sparse retrieval |
| Pool/RRF | `retrieve(..., pool=25)`; hybrid takes 50 from each branch, RRF constant 60, default weights 1/1, keeps 25; rerank over all 25 | `run.py` does not pass the pool from the config: adding a YAML field does not make it take effect. `k` does not change the pool and does not make the model rerank only 5 |
| Zero lexical scores | `_rank` still returns chunks in a stable order, even when no term matches | BM25 scores ≤0 must be removed before building the lexical ranking for both BM25 and hybrid. Avoid treating arbitrary file order as lexical evidence, especially for VI→EN |
| Reranker | SentenceTransformers CrossEncoder taking a revision, `max_length=512` for the whole query–passage | No log of activation/logits, pair truncation or visible tokens. Raw logits must be verified and sigmoid applied exactly once if needed |
| `corpus.py` | Only `.md/.txt/.pdf`, each PDF page/`\f` split separately; the splitter uses character `len()` | `800/100` is characters, not model tokens. The splitter does not guarantee an 800 ceiling: it may keep passages close to 1600 characters. DOCX is not loaded |
| `metrics.py` | Recall on `{doc,pages?}` targets, hit, MRR to the depth actually returned; nDCG@10 | `is_hit` only accepts the first matching target; document/page is not enough to prove the right span. nDCG adds the gain of several chunks for the same target but IDCG uses the target count, so it can exceed 1. Do not use the current nDCG for conclusions |
| Refusal sweep | Sweeps the top score over every question in the file; BM25 score, the hybrid dense cosine of the RRF top chunk, or the reranker score | No dev/test split, coverage or output quality; `false_answer` is only a proxy for accepting unanswerable questions. Do not use this sweep to choose a threshold from test |
| `run.py` and artifacts | `run.json`, `metrics.json`, `per_question.jsonl`, `report.md`; commit/config/count/machine, aggregate retrieval latency | Ranked chunk IDs, each score type, the candidate pool, contexts/outputs, peak RAM, stage timing, split/subset and the corpus hash are not stored. The commit does not describe a dirty working tree |
| Resources | The index holds both dense and BM25 even for the BM25 configuration; a dictionary keeps several indexes/models in the same process | Do not take the current index build time as BM25's necessary cost. Run each embedding and the reranker in stages, freeing models; measure cache hits/misses separately |
| `eval/tests/test_eval.py` | Smoke tests, page constraint, RRF and simple sweeps | Not enough to prove many-evidence, nDCG without double counting, the Qwen instruction, split leakage or correct answer-level behaviour |

Also compared `services/ai-qa-service/src/db/repositories/chunk_repo.py`: the function named `bm25_search` uses PostgreSQL `ts_rank`/`plainto_tsquery('simple', ...)`, unlike the eval scorer. The results proposed here describe the **offline harness**; they do not yet represent the deployed stack or the product's warm TTFT. Read `AGENTS.md`, `docs/README.md`, the two required reports and the `.agent/context/README.md` index; no service contract changed.

## 3. A shortlist based on official sources

Sources checked on **19/10/2026**. The specification column is fact from the authors; the choice column is an inference for the SOPilot experiment, not a CPU benchmark or a project quality result.

| Role | Model and source facts | Reason to keep / limits of the inference |
|---|---|---|
| E0: dense baseline | `BAAI/bge-m3`: MIT, 1024 dimensions, supports >100 languages, 8192 architectural context. [BAAI model card](https://huggingface.co/BAAI/bge-m3), [BGE-M3 paper](https://arxiv.org/abs/2402.03216) | A multilingual control already in the harness, needing no query instruction. Dense only; its sparse/ColBERT abilities do not count as a benefit in this test |
| E1: dense challenger | `Qwen/Qwen3-Embedding-0.6B`: Apache-2.0, 0.6B, >100 languages, 32K context, output up to 1024 dimensions. [Qwen model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [Qwen3 Embedding paper](https://arxiv.org/abs/2506.05176) | A challenger from another family, with cross-lingual retrieval and query instructions. The 0.6B version limits cost; parameter count/context/leaderboard do not prove it is faster or better than E0 on VI→EN SOPs |
| R: the only reranker | `BAAI/bge-reranker-v2-m3`: Apache-2.0, a multilingual cross-encoder scoring query–passage; the official example uses pair max_length=512. [Reranker model card](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Suits rerank on/off for both EN and VI queries on EN passages; a local call path exists. No extra reranker per embedding family, no comparison of managed providers |

No E5/third model in the core round. Both embeddings output only **one dense vector** per chunk; BM25 uses the same corpus separately. No long-context, Matryoshka, sparse BGE, ColBERT, fine-tuning or quantization tests in this matrix. Model licenses do not replace the corpus license.

### 3.1. Instructions, pooling and scores to record in the manifest

- **E0:** no query/document prefix; CLS dense pooling and L2 normalization. Lock dense-only; with FlagEmbedding, `return_dense=True`, `return_sparse=False`, `return_colbert_vecs=False`. Check against the [official BGE-M3 implementation](https://github.com/FlagOpen/FlagEmbedding/blob/master/FlagEmbedding/inference/embedder/encoder_only/m3.py); do not substitute generic mean pooling for every model.
- **E1:** last non-padding token pooling, L2 normalization, 1024 dimensions. Queries use exactly the template `Instruct: {task}\nQuery:{query}` per the [Qwen usage](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B). A fixed EN task for both EN/VI queries: `Given a question in English or Vietnamese, retrieve English passages that contain evidence to answer the question.` Documents have no instruction. Use the model's adapter at the right version; check dependency compatibility (the card says Transformers ≥4.51.0), without assuming the minimum dependencies in `pyproject.toml` suffice.
- **R:** the input is the raw query and the EN passage, without an embedding instruction. Rank by raw logit; record the actual activation name. If the gate uses sigmoid(logit), apply it exactly once; it is only a monotonic transform, **not a probability of being answerable/correct/having enough evidence**. Lock the same revision and tokenization between dev/test scores. [BAAI reranker usage](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- Dense retrieval uses cosine through the dot product of two L2-normalized vectors; never mix indexes even though both models have 1024 dimensions. Pin the real model/tokenizer commit SHA when preparing the run; this report does not invent unchecked revisions.

## 4. Data, splits and the answer-level subset

Notation: **N** = the number of reviewed query variants; **G** = the number of relatively independent question groups, merging same-meaning EN/VI, paraphrases and closely related questions about the same content. N is not G. The corpus/chunks are fixed and used for every query; only **questions** are split, never removing test evidence from the corpus.

1. Workstream 02 keeps the expected direction of ≥100 queries from workstream 01/the proposal; this is not an existing data count or a power guarantee. The smoke set of 3 documents/9 questions is not a research dataset.
2. Split by group G, seed `20261019`, targeting about **30% dev / 70% test** by query count. Merge near-duplicate section/policy source groups before splitting; EN/VI pairs never fall into two splits. Report the real G and N, and deviations from the ratio due to keeping groups whole and the source distribution.
3. Both dev/test have EN→EN and VI→EN, answerable/near-topic unanswerable; try to have single-evidence questions and a small multi-evidence group. No query translation in retrieval. If the dataset has paired EN/VI, keep the pair ID and analyse paired; not every query needs a translation.
4. Define **S_dev, S_test** before seeing rankings/outputs: stratified random samples from each split, targeting `|S_dev|≈min(N_dev,20)`, `|S_test|≈min(N_test,40)`. Keep whole EN/VI/paraphrase groups, rounding down to the budget if needed. Aim for balanced language × answerability cells: about 5 per cell in dev, 10 per cell in test if the data allows. Among answerable questions, aim for about 20% needing multiple evidence. These are design quotas, not existing counts.
5. If a cell lacks samples, take every valid sample of that cell and record the shortfall and the real count; do not duplicate queries to fill quotas or pick questions by score/winning model. Report the subset's G; with too few groups, the conclusion is exploratory. Store subset IDs/seed/hash before running the comparison conditions.
6. S_dev output labels are used for calibration; **S_test is not used to choose prompts, models, chunking or thresholds**. Lock gold and the design before opening test results. Operators may run retrieval on test to collect artifacts after locking, but must not use it to go back and tune.

S = S_dev ∪ S_test, usually targeting at most about 60 query variants, with no commitment to the number until workstream 02 verifies it. The subset is class-enriched for quick review, so coverage/risk on S only describes S's distribution. With known sampling probabilities, weighted estimates for the original test can be added; do not call a balanced 50/50 coverage the real deployment rate.

## 5. Relevance and metrics

### 5.1. Evidence instead of file-name matching

The gold of each answerable question consists of one or more **sufficient evidence sets**. Within each set, the evidence units are mandatory (AND); one unit may have several equivalent alternative spans (OR). Two different sufficient sets are also OR. For example, when both the leave eligibility condition and the notice deadline are needed, finding many chunks restating the condition is still not two units.

Each span has document/version/hash, page or heading and offsets/quote; it is mapped to chunk IDs **after** chunking is locked. It is a hit only when the text the system actually sees contains the required content in full, not merely the same page. One chunk may satisfy several units; several chunks satisfying one unit count once. If one piece of evidence is split, the gold must specify the sufficient chunk/span combination, not count each half as a full hit.

For question q, sufficient set j has m_j units, and C_j(k) is the number of units satisfied by the top-k:

- `EvidenceRecall@k(q) = max_j C_j(k)/m_j`.
- `AllEvidence@k(q) = 1` when some set j is fully satisfied; `AnyEvidenceHit@k(q) = 1` when at least one unit is found.
- Take the max over **one sufficient set**, never adding incompatible fragments from several ways of answering. With a single set, this is recall over evidence units.

Gold must be checked by reviewers independently of the winning configuration; store disagreements/adjudication. Unanswerable questions need a review of the whole valid corpus, not just a few top chunks. If pooling is used to find more evidence: merge the top-25 of all five retrieval configurations and the rerank results within S, hide system names, and add source checks; qrels based on an incomplete pool must be stated. Gold fixes after seeing test only correct labelling errors with a log, then recompute **every** configuration; never tune the system to the corrected gold.

### 5.2. Primary and secondary metrics by RQ

| RQ | Primary metric / population | Secondary metrics and limits |
|---|---|---|
| RQ1 | Macro **EvidenceRecall@5** on answerable test, hybrid–dense and hybrid–BM25 | AllEvidence@5, AnyEvidenceHit@5, EvidenceRecall@10/@25, MRR@25 of the first evidence; report the two directions and sample sizes separately. MRR does not prove finding enough multiple evidence |
| RQ1b | The same Recall@5 difference split into EN→EN, VI→EN | With meaning pairs: the difference in hybrid's effect between VI/EN queries; do not assume VI BM25 is always 0 |
| RQ2 | **Grounded answer success** rerank-on minus off, on answerable S_test, gate off | Recall@5/AllEvidence@5 on S_test; correctness, faithfulness, citation precision/completeness, self-refusal, rerank time. Ranking gains and answer gains must be concluded separately |
| RQ3 | **Output selective risk** with coverage at the locked τ over all of S_test | False refusal, false acceptance, overall wrong-accepted rate, utility/correct-answer yield, results per class/language and confusion counts; no score proxy in place of outputs |
| RQ5 | The Recall@5 difference E1–E0 in **dense** and **hybrid**, answerable test | AllEvidence@5, resources and the interaction `Δ_hybrid−Δ_dense`; do not claim the best embedding from dense alone or leaderboards alone |

Recall is averaged only over answerable questions; unanswerable questions with zero gold are not assigned recall=0 and mixed into the mean. Macro by query, reporting N/G separately; results by semantic group are an additional sensitivity analysis. When the top-k contains fewer than k candidates, use the real count without padding with non-matching chunks.

Do not use the current `ndcg@10` as a core metric. Add **standard nDCG@10** as a secondary analysis only when workstreams 02/04 have unique chunk qrels, a relevance/gain definition with IDCG in the same unit, tests of the [0,1] domain, and handling of overlap and depth; do not silently call a new evidence-based gain metric standard nDCG. Fixing nDCG need not block the whole study if EvidenceRecall/AllEvidence/MRR are verified.

### 5.3. A real-output rubric for RQ2–3

Reviewers see the query, gold spans/reference, the context **given to the generator**, the output and citations; config/model names hidden and condition order shuffled. Review both non-rerank and rerank outputs on the same S, including unanswerable ones. The reference guides checking; it does not force string or wording matches.

- **Correctness/completeness:** meets the requirement with the important conditions/figures; record correct / partial / incorrect. Partial counts as not successful in the main binary metric.
- **Faithfulness:** split into atomic factual claims; mark supported / contradicted / unsupported against the given context. A claim true outside the corpus but without grounding is still not faithful. Report the supported share and the share of answers with a wrong/unsupported claim.
- **Citation precision:** the share of claim–citation pairs pointing to the right location and a source that really supports the claim; **citation completeness:** the share of claims needing citations that have at least one supporting citation. The right URL/document with an unsupporting span is an error. Report the per-question macro and raw counts; an empty denominator is N/A, never an automatic 100%.
- **Grounded answer success = 1** when it actually answers, correctness is complete, every important factual claim is supported by the context and has a supporting citation; otherwise 0. This is a metric defined by the project, not vouched for by an automatic judge or the ALCE name. Self-refusal on an answerable question counts 0.
- **Wrong answer = 1** for an output that actually answers but is incorrect/partial or has an unsupported claim. Pure citation errors are reported separately; a missing citation is not equated with every kind of content error. Add the share of answered outputs failing grounded success, to include citation errors.

Separating correctness and citation follows [ALCE (Gao et al., EMNLP 2023)](https://aclanthology.org/2023.emnlp-main.398/); the EN/VI rubric here is applied by human reviewers, without assuming the paper's automatic evaluator has been validated on SOPilot. Use at least one reviewer who knows VI/EN; with a second person, prioritize reviewing every disagreement/error/refusal case and at least 20% of outputs sampled at random, reporting agreement before adjudication. With a single reviewer, publish the limitation and do not invent inter-rater agreement.

## 6. Control variables and the retrieval budget

| Variable | Locked for the core round | Why / what is recorded |
|---|---|---|
| Corpus | One EN snapshot, fixed extraction and access rights, checksums of both source and text | No corpus translation; documents do not change between configurations |
| Chunking | Start with paragraph/page-aware `size=800, overlap=100` **characters** to inherit the harness; add a shared token ceiling check before freezing | If a long passage exceeds the ceiling, split it further at a sentence boundary once for every model; no per-model chunking, no sweep over sizes |
| Shared chunk ceiling | Each chunk ≤384 tokens under **each** tokenizer of E0/E1/R; title metadata, if included, also within the budget | Choose shared text boundaries satisfying every tokenizer. 384 is a design budget keeping pairs short, not a claim about the architectural limit |
| Query | Verbatim, no rewrite/translation; query embedding ≤128 tokens including instruction/special tokens, raw reranker query ≤96 tokens | Overly long queries are shortened by the author before freezing, never silently truncated in a meaning-changing way; log lengths per tokenizer |
| Encode/pair | Embedding cap 512; reranker **total pair** cap 512, preserving the query, cutting the passage end if necessary | Assert the real pair length including special tokens. The core round aims for no truncated evidence; errors must be fixed in chunks/scope before test. Store the visible text and truncation rate, not only the max length |
| Dense | Exact cosine, L2 query/document, dimension=1024 for both E0/E1 | No ANN recall/quantization as a confounder |
| Lexical | The eval BM25 implementation: NFC/lowercase, unigrams+bigrams, k1=1.5,b=0.75, no stemming, diacritics kept | No per-language tuning; remove scores ≤0. State the lexical variant clearly and that runtime parity is not achieved |
| Branch depth | Dense top-50, BM25 top-50 positive-score; bounded by the real chunk count C | This is the fusion input, distinct from the rerank candidate pool |
| Fusion | `RRF(d)=Σ_b 1/(60+rank_b(d))`, ranks starting at 1, weights 1/1; a chunk absent from a branch contributes 0 | Keep the constant 60, no weight sweep. This is a baseline from the [original RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), not an optimum measured on SOPs |
| Candidate pool P | Top-25 after dense/BM25 or fusion; hybrid union ≤100 then keep 25 | Rerank only reorders **the same** P, adding no candidates; store chunk IDs, per-branch rank/score, RRF, rerank logits |
| Context/output k | Top-5 after ranking, with the same context budget of 2560 generator tokens and at most 512 output tokens | If it does not fit the budget, use one fixed packing rule by rank and record the evidence actually visible; do not let the provider silently cut the prompt. Lock the rule before test |
| Ties/dedup | Stable chunk ID as the tie-break; the same chunk ID appears only once | No random file order; overlapping chunks do not raise recall for the same evidence |
| Runtime | CPU FP32, inference/eval mode, models loaded sequentially; initial batch 4, query batch 1, threads fixed after the dev pilot | Do not copy GPU FP16/FlashAttention from examples. Batch may be reduced for RAM during the pilot, then locked; report each model's parameters separately |

The constants 50/25/5 stay close to the harness to reduce change effort. Measure **candidate EvidenceRecall@25/AllEvidence@25** before rerank and Recall@5 after: the reranker cannot rescue evidence already excluded from P. If P=25 is too slow, record the dev pilot and P=15 may be settled for **all** of the relevant H0/H0R before test, updating the manifest; never choose P per query or after seeing test. If a model cannot run, report the corresponding RQ as lacking evidence rather than silently substituting a third model.

Resource measurements include load/cold start, corpus embedding once per model, query embedding, BM25/dense/fusion, rerank, context packing and API generation; peak process RAM, wall time, CPU/threads, p50/p95 with n. The cache reduces effort, but query benchmarks must distinguish cached/uncached; do not substitute cache lookup for query encoding and call it real latency. Do not add variable API time into conclusions about embedding speed. This offline measurement does not guarantee TTFT/NFRs.

## 7. A fixed generator and the refusal design

### 7.1. One API generator for every answer-level condition

Choose **one API model ID/version with free quota available** at run time; the provider need not be chosen to lock the method. Do not assume an unlimited free tier or a specific quota. Lock the model/version, system/user prompt hash, context template/citation IDs, temperature=0 if supported, top_p, seed if supported, context/output limits, retry policy and response metadata. The same generator answers in the query's language, using EN context. Temperature 0 does not guarantee full determinism.

The shared prompt: answer only from the context, without external knowledge; state the important conditions, cite `[chunk_id]` for each factual claim; refuse clearly if evidence is missing. **The prompt does not change between rerank off/on or between τ values.** The final prompt and 2–4 format-check examples from dev are locked before test; test gold never goes into requests. Reviewers see the real context, not only the top-k IDs.

Generate raw outputs **once per query × the two context conditions H0/H0R** within S; cache requests/responses verbatim. The expected number of useful generations is `2|S_dev|+2|S_test|`, about 120 if the target subset quota is met, not multiplied by thresholds or the two embeddings. The dev pilot may be reused if it used the final prompt; every output from an old prompt must be replaced together. Retries only for transport/rate limits, bounded, never because an answer is bad. API errors/timeouts are missing, not counted as correct refusals; report the number of lost pairs, and do not analyse one side as paired. When the provider loses the model/quota: checkpoint and wait, or a new research version reruns **every affected comparison condition**; never mix generators.

### 7.2. The pipeline and threshold for RQ3

Lock RQ3 on **H0R = BGE-M3 hybrid + reranker R**, not on the pipeline that wins after seeing test. RQ3 does not simultaneously change the embedding, retriever, reranker or generator. The gate score `s(q)=max raw reranker logit` in pool P, i.e. the top-1 score after rerank; an empty pool must refuse. The gate accepts if `s≥τ` and refuses if `s<τ`. RRF is not used as confidence; τ is not transferred to cosine, sigmoid or another model without recalibration.

The baseline `τ=−∞` is **gate-off / accept every query with a pool**; it does not guarantee the generator always answers: the generator may still refuse by itself under the same prompt. Record gate refusals and generator refusals separately. Do not call this baseline "always answer" if the real outputs include refusals; forcing the generator to answer with a different prompt would add noise and is outside the core.

For each reviewed raw output, store `a` (gold answerable), `r_gen` (the generator actually refused), `w` (wrong/unsupported answer), `g` (grounded success). For threshold τ, set `cτ=1` when the gate accepts **and** the actual output is an answer; all other cases are final refusals. The offline replay only replaces outputs blocked by the gate with a fixed refusal message, without editing the answers kept.

With n=|S|, A/U the gold answerable/unanswerable sets, n_A/n_U their sizes, report raw numerators/denominators:

| Final output metric | Formula / reading |
|---|---|
| Coverage | `Σcτ/n`; plus gate acceptance `Σ1[s≥τ]/n` to see the generator's self-refusals |
| False refusal | `Σ_{q∈A}(1−cτ)/n_A`, including gate and generator; also broken down by the two causes |
| False acceptance | `Σ_{q∈U}cτ/n_U`; plus gate-only acceptance on U; this is not a correctness measure for every answerable question |
| Selective risk | `Σ cτ·w / Σcτ`: content/faithfulness errors among the outputs that actually answer, including errors on A |
| Wrong-accepted rate | `Σ cτ·w/n`: the number of queries accepted with a wrong answer over the whole subset |
| Correct-answer yield | `Σ cτ·1[correct and faithful]/n`; plus the grounded-success yield to see citation errors |
| Unanswerable refusal | `Σ_{q∈U}(1−cτ)/n_U`; must be read together with false refusal and coverage |

An output giving content on an unanswerable question counts `w=1` against the locked corpus; empty/evasive answers must be classified explicitly by reviewers. A 0 denominator is reported as N/A. The answerability confusion table does not replace the output quality table. Risk–coverage is a description from [selective classification](https://arxiv.org/abs/1705.08500); the gate score here is not calibrated as a probability nor does it carry the paper's statistical guarantees.

### 7.3. Choosing τ on dev, locked before test

1. Use only H0R scores and **output labels on S_dev**. The candidate thresholds are midpoints between distinct dev scores, plus −∞/+∞; use full precision, without rounding before the decision. This is a cheap sweep over cached outputs.
2. Proposed design rule: among τ with **real coverage ≥0.50** and **false refusal ≤0.20** on S_dev, choose the τ with the smallest wrong-accepted rate. On a tie, choose higher coverage; if still tied, the lower τ. The two constraints are operating goals proposed by workstream 03 to avoid refusing almost everything; they are not proven standards or approved product targets.
3. If no τ is feasible, keep gate-off as the control and report **no operating point meets the constraints**. Do not relax the constraints on test. If a τ exists but the dev improvement is too small/the CI wide, still report the trade-off and uncertainty; do not assume H3 is true.
4. Record a manifest with τ*, the score/activation definition, revision, dev/subset/prompt hashes, constraints and the freeze time; then run/evaluate S_test once with τ* and gate-off. Report the achieved coverage/false refusal/false acceptance/risk on test even if worse than dev.
5. The full test risk–coverage curve may be plotted after locking as a descriptive analysis, marking the chosen τ*; do not choose a new operating point from the test curve. One shared τ for both EN/VI to reduce tuning; report the directions separately, without creating per-language thresholds after seeing results.

The replay over real outputs on S answers the quality question for selective answering; it does not measure API calls/latency saved in the real system. A gate deployed before generation could avoid API calls, but that call path needs its own check. The top-1 score does not know for certain that there is enough multiple evidence; this limit must be recorded if the gate accepts questions with only partial evidence.

## 8. Paired comparisons, uncertainty and decision rules

### 8.1. Analysis locked before test

- Compare the same query IDs/context budget, using per-query deltas and win/tie/loss. Resample **groups G** (keeping EN/VI/paraphrases together) in a paired cluster bootstrap, 5000 times, fixed seed, for 95% CIs of the deltas and the rates/risk/yields. Do not resample claims or two translations as independent. Report N, G and the number of discordant groups; with few groups the CI is unstable and power insufficient, which must be stated.
- For the subset: bootstrap S's groups, keeping the same output pairs. For RQ3 test, keep τ* fixed in every resample; do not retune with the test bootstrap. This CI is conditional on the dev threshold and dataset; it does not include every uncertainty from source selection, question translation or annotation. A dev bootstrap re-choosing τ may be added as a sensitivity analysis, not a condition for the quick run.
- If p-values are needed for confirmatory conclusions, use a paired randomization/sign-flip test by **group**, with the same metric definition; avoid independent t-tests on query variants. p-values may be omitted if only effect+CI are reported and described cautiously. [Dror et al., ACL 2018](https://aclanthology.org/P18-1128/) is the basis for choosing a test that fits the design, not a guarantee for this particular dataset.
- Separate families: the two RQ1 contrasts (H0−D0, H0−M) and the two RQ5 contrasts (D1−D0, H1−H0); if p-value-based claims are made, use Holm within each family. The RQ2 primary output and the RQ3 operating point are different questions; do not pick only the favourable metric. Language/secondary metrics are exploratory; do not use many slices to claim an overall win.
- Record the paired delta CIs in **absolute percentage points**, not relative percent. A lack of statistical significance does not prove equivalence. No power claim from the expected N; one binary change on a small test subset may already be several percentage points.

### 8.2. Practical improvement levels and choosing a configuration

The levels below are **design decision rules set before test**, not results, standards from papers or owner-approved PRD targets:

| Decision | Level of interest and rule |
|---|---|
| RQ1 hybrid | Recall@5 up ≥0.03 absolute over the baseline compared; only a CI of the delta above 0 counts as evidence of improvement. To say hybrid beats both, it must hold for both D0 and M; beating BM25 alone is not enough |
| RQ2 rerank | Grounded answer success on A of S_test up ≥0.05 absolute; only a delta CI above 0 supports an output improvement. If only ranking improves, conclude ranking-only. Report the extra time/peak RAM; if the effect is unclear and slower, choose off for the fast configuration |
| RQ3 refusal | Prefer cutting the wrong-accepted rate by ≥0.05 absolute against gate-off, with the error delta CI below 0, together with coverage ≥0.50 and false refusal ≤0.20 on test |
| RQ5 embedding | E1 is worth switching to if hybrid Recall@5 rises ≥0.03 with a CI above 0, VI→EN has no practical drop ≥0.03, and resources fit the locked pilot budget; dense alone is for explanation, not a substitute for the hybrid contrast |

If the sample is too small to distinguish these levels, report insufficient evidence rather than inflating the effect by picking easy questions. Report both the point estimate and whether the CI contains the practical level; a point estimate beyond the level with a wide CI is still not confirmed. The 0.03/0.05 levels must not change after seeing test.

Operating rule: settle the proposed configuration **on dev**; test only verifies, never used to search for new configurations. The default order is E0 hybrid; if dev shows no practical benefit over dense, dense may be proposed for the demo, but RQ1/2/3 keep their predefined contrasts. Choose E1 only if dev meets the quality/resource rule; with large uncertainty keep E0 as the existing baseline, without calling E0 the winner. If rerank is not needed to improve outputs, propose off; RQ3 on H0R remains an independent research result, and its threshold is not transferred to another demo configuration automatically.

The dev pilot measures free RAM/time to lock the real budget, without asking the owner again about hardware/deadlines. Load only one heavy model, avoiding prolonged swapping; if it fails, checkpoint and report conditional feasibility. Use a quality–time–RAM Pareto view: with an unclear benefit, prefer the existing lower-cost configuration. Do not assign fake millisecond budgets as if measured; p95 from a few dozen queries must report n and does not count as meeting public NFRs.

Valid conclusions include: supporting a hypothesis within the sample; negative/reversed results; or insufficient evidence because of CIs/data gates/tooling. A refusal that reduces errors but drops coverage or raises false refusals is a trade-off that misses the operating goal; do not dress it up as success. The draft targets Recall@5≥0.80/citation precision≥0.85/correct refusal on U≥0.80 from workstream 01 are reported separately; they do not replace the contrasts or legitimize a system that refuses everything.

## 9. The minimal run sequence after handover

1. Workstream 02 hands over the EN corpus snapshot, question groups/splits and span gold; workstream 04 verifies the metrics, positive-score lexical filtering, adapters/instructions, provenance and output export. If not ready, stop the affected conclusions; do not use smoke in place of data.
2. A short dev pilot of 4 queries covering both directions and A/U to check token visibility, pooling, scores, RAM/batch/threads and the prompt/citation format. Do not use the pilot to try many models. Lock the manifest/chunks/split/subset/metrics/budget; do not read test results to choose.
3. Encode the corpus once with E0, cache query vectors and full rankings; run D0/M/H0. Encode E1 in another process/stage, run D1/H1; do not re-embed for BM25. Query vector/rank caches may be used to avoid recomputing costs across configs.
4. On S, take **exactly H0's P**, store it, then run R once per pair; H0R reorders P. Pairs `Σ_{q∈S}|P_q|≤25|S|`; do not rerank all N to save CPU. The RQ2 retrieval layer also only represents S; do not claim the whole test was measured.
5. Generate two raw outputs per query on S, reviewed per §5; use S_dev to choose τ, locked before opening S_test labels/output quality. RQ2 gate off; RQ3 replays H0R with the same reviewed outputs. No calls per τ or for E1.
6. Compute paired test deltas/CIs, by language and by error type (multi-evidence/truncation/candidate miss/generation/citation/refusal); report real costs. Missing data, API errors or RQs not run are left empty with a reason, never with invented results.

Design cost: two corpus embeddings over C chunks, at most 2N query embeddings (cache shared by dense/hybrid), five retrieval rankings per query, ≤25|S| reranker pairs, about 2|S| useful generations and output reviews. RQ3 does not multiply generation cost. No minutes/hours are committed before measuring the CPU and C/N.

## 10. A handover contract that does not depend on waiting for other workstreams

### 10.1. For workstream 02 — data

- Provide the original EN corpus with usage rights, snapshot/version/license/URLs/hash, text extraction and topic boundaries; the real C/N/G. No corpus translation required; VI queries/references need content review against the EN evidence.
- Group IDs merging semantic pairs/paraphrases/near-duplicate source sections; dev/test splits and subset IDs by the stated seed/strata. Hand over counts by language×answerability×single/multi-evidence and the number of independent groups, stating any missing cells.
- Gold sufficient evidence sets/alternatives, source-stable spans, answerability over the whole corpus/access scope, references/key facts; map chunks after freezing, and check visible spans after tokenization/context packing. `{doc,pages}` is not sufficient final gold.
- Prepare near-topic unanswerable questions (missing rules, missing conditions/figures, false premises), not only off-topic questions. Check answerability across the whole corpus, keeping reviewers and the disagreement history.
- Enough evidence to read EN/VI pairs without treating the two questions as two independent observations; do not invent counts/review status before the artifacts exist. If the data design deviates from the proposed ratios, report the real numbers and reasons before test; do not cut the answer-level scope down to retrieval-only.

### 10.2. For workstream 04 — tooling

- Make branch depth/pool/k, weights/RRF constant and lexical positive-score filtering effective; store candidate IDs/hashes before/after rerank. Test the same P on/off, BM25 zero-match cases, ties and candidate misses.
- E0/E1 adapters with the right pooling/prefix/L2/dimension, pinned revisions/runtime; enforce shared chunks/token caps and visible text; test that instructions are query-only and Qwen's last non-padding pooling. Do not download/run models just to finish workstream 03's document.
- Evidence metrics supporting AND/OR alternatives, one chunk with several evidence units and several chunks for the same evidence, combined split spans; test bounds/duplicate invariance/MRR depth/empty-gold N/A. Fix the broken nDCG or remove it from conclusions; renaming the column is not enough.
- A split/subset manifest and a guard against tuning on test; separate the gate score from dense/RRF/rerank scores. The sweep has ±∞ endpoints, a tie policy, coverage/confusion/raw denominators and a τ freeze; retrieval proxies must be labelled as proxies.
- Add answer request/context/output/citation export, reviewer labels, gate replay and an API missing/error log. Store the generator ID/version/prompt hash/decoding/usage/time; never store secrets. Check one model and prompt for every comparison condition.
- Provenance includes the code commit **and the dirty diff/file hashes**, corpus/chunk/qrels/split/subset/config hashes, revision/tokenizer/pooling/length/dtype/threads/batch/packages, the score activation and the cache fingerprint. The current untracked files are not reflected by HEAD alone.
- Instrument stage timing/peak RAM/cold-warm/cache; avoid holding both embeddings and the reranker at once. BM25 should not need to load/embed dense in order to report an independent lexical cost. Check offline/runtime lexical parity separately if deployment results are reported.

These are tooling requirements for workstream 04, not a claim that they are fixed. No ticket opened or PLAN updated in this session. Workstreams 05/06 can use §9 and the rubric to execute/verify once the data/tooling gates are met; workstream 03 need not wait for them to settle the shortlist/methods.

## 11. Final shortlist, final matrix and decisions still to reconcile

**Final shortlist:** E0 `BAAI/bge-m3` dense; E1 `Qwen/Qwen3-Embedding-0.6B` dense; R `BAAI/bge-reranker-v2-m3`; one fixed free API generator, provider not yet chosen. No third model, no second reranker, no full factorial embedding×retriever×reranker×gate×generator.

| ID / comparison | Configuration | Where retrieval runs | Reviewed outputs | RQ answered |
|---|---|---|---|---|
| D0 | E0 dense, rerank off | All N, dev/test reported separately | No | RQ1 baseline; RQ5 dense baseline |
| M | BM25, no dense inference needed | All N, one shared lexical result | No | RQ1 lexical baseline |
| H0 | E0 dense + BM25, RRF 1/1, rerank off | All N; P stored for S | One output per query on S, paired with H0R | RQ1 hybrid; RQ2 off; RQ5 hybrid baseline |
| D1 / H1 | E1 dense / E1+BM25 RRF, rerank off (**two** configurations) | All N, reusing BM25 | No | RQ5: D1−D0 and H1−H0 |
| H0R | H0 + R on the same P, gate off | S_dev/S_test only | One output per query on S, paired with H0 | RQ2 on−off: retrieval and answer level |
| H0R(τ*) vs H0R(−∞) | Same retrieval/rerank/generator; only the gate enabled | Replay of scores/outputs on S; τ from S_dev, locked before S_test | Reuses the reviewed H0R outputs, no new generation | RQ3: output risk, coverage, false refusals and wrongly accepted answers |

That makes **5 whole-set retrieval configurations + 1 rerank configuration on the subset + 1 gate replay**; the number of table rows is not the number of models/indexes/API runs. RQ1/RQ5 have no answer-level conclusions in the minimal matrix; RQ2/RQ3 generalize only within the reviewed subset.

| Point still to reconcile at execution | Default/target handed over | Who provides the evidence |
|---|---|---|
| Corpus source and real sample/split/group counts | EN corpus; N/G/C not verified; the §4 formulas | Workstream 02, within the source boundaries the owner chose; no re-asking about deadlines/hardware/the proposal |
| Span gold and the capacity to review the subset | AND/OR evidence sets, S_dev≈20/S_test≈40 with both directions/A-U | Workstreams 02/06; if short, record the limitation, without dropping output review |
| Revision/tokenizer/pooling, truncation and score activation | Per the §3 sources, the §6 caps; frozen before test | Workstreams 04/05; unpinned default revisions do not count as reproducible |
| Whether the tool gates are ready before measurement | Candidate export, positive lexical filtering, evidence metrics, dev/test guard and replay | Workstream 04; the current harness does not meet them all |
| Generator/model version and real free quota | One model/prompt for every answer condition, about two useful calls per query in S | The running workstream chooses at execution; on running out of quota, checkpoint, without changing generators between conditions |
| CPU/batch/threads and the real time/RAM budget | A short dev pilot, sequential model loading, P=25 by default | Workstream 05; P=15, if needed, must be locked for the whole comparison before test |
| Operating goals/effect sizes | §7–8 are concrete proposed rules, not proven product targets | Locked in the run manifest before test; changes must be versioned, never tuned on test |

The points above are execution inputs and evidence limits; they do not reopen choices the owner has settled. This document completes workstream 03 at the method level; there are no runs, output labels or results yet to conclude on H1/H2/H3/H5.
