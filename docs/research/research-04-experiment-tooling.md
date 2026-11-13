---
id: RESEARCH-04-experiment-tooling
title: "Workstream 04: experiment tooling, gaps and a minimal fix specification"
status: final
type: research
scope: research
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
refs:
  - docs/research/research-01-scope-and-rqs.md
  - docs/archive/handoffs/HANDOFF-research-workstreams-2026-10-18.md
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. It describes the code snapshot of 2026-10-19 (V1 services and the early `eval/`); file:line references are to that snapshot. Paths under `.agent/` and `AGENTS.md` are as they were at the time.

# Workstream 04 research tooling handoff

## 1. Conclusions and survey limits

**`eval/` can be reused, but is not yet fit to run the official experiments.** The nDCG-above-1 bug was reproduced with the existing function. The harness does not store rankings/context yet, has no answer-level runner/checkpoint, and does not fully lock embedding provenance. The runtime differs from offline on the lexical scorer, score gate, chunking and how the reranker is wired; eval results cannot yet be read as system quality.

The shortest path is to finish an independent offline harness, add a checkpointed generation API path for a defined subset with reviewed outputs; runtime verification is a separate track. PostgreSQL, ingestion, the gateway or the full stack need not be preconditions for starting retrieval research.

Scope inherited from the owner: the original EN corpus; EN/VI queries (EN→EN, VI→EN), no corpus translation; dense/BM25/hybrid; two embeddings; one reranker on/off; refusal and a human-reviewed answer-level subset; 32 GB total RAM, CPU, a generator through a free API when actually run. Quotas, speed and which models fit have not been verified. No corpus, shortlist, sample count, k, pool or threshold is chosen on behalf of workstreams 02–03.

`final` only completes this survey/specification; it does not certify that the tooling is fixed, that research has run or that the PRD/ADR/PLAN are approved. Workstreams 02–03 run in parallel; this document uses the parameterized contract in §5 and records reconciliation points, without waiting for or editing their outputs.

Git was checked before any action: branch `fix/auth-google-roster-admission`, many staged/unstaged/untracked changes, including an untracked `eval/`. The target file did not exist, so there was no old content to merge. The session only added this file, did not change branch/commit, did not read `.env`, did not download models, did not call APIs and did not run the stack. The evidence is the working tree snapshot of 19/10/2026; the HEAD commit alone does not represent the code surveyed.

Read `AGENTS.md`, `docs/README.md`, the workstream 01/overall handoffs and the context `.agent/context/README.md`, `architecture/system-overview.md`, `database/schema.md`, `database/tables/{knowledge,conversation}.md`, `authorization/dual-strategy.md`, and the ownership/retrieval part of `service-boundaries/responsibilities.md`. The context has drift: the rerank/schema descriptions and the `to_tsvector('english', ...)` example do not prove the runtime. The DDL `infrastructure/init-db/003_knowledge.sql:126` uses `simple`; the running DB state was not checked. The skill `.agent/skills/analyze-quality/SKILL.md` was applied to classify evidence; the HANDOFF name/path was kept at the owner's request.

## 2. Tracing the real code

The paths and lines below are from the repo root, per the snapshot read in the session. This is static evidence; only the checks in §4.2 were executed.

### 2.1. Offline eval

| Call point | Evidence file:line | Wired behaviour / consequence |
|---|---|---|
| CLI → run | `eval/sopilot_eval/run.py:160–170`, `45–49` | Parses dataset/config/out; reads every question in `questions.jsonl`, loads the corpus. No dev/test split selection, no schema validation or subset filtering |
| Corpus → chunks | `eval/sopilot_eval/corpus.py:21–27,30–56` | PDFs take text per page; MD/TXT use form feeds, usually the whole file is page 1. Only reads files directly in the folder, not recursive, no DOCX. Chunks by characters/paragraphs, not by tokenizer; only doc/page/text, no section/span/durable chunk ID yet |
| Config → index | `run.py:60–71`; `embedders.py:110–120`; `retrievers.py:41–52` | Every config, BM25 included, builds the embedding matrix and BM25. There is a corpus cache; query embeddings are recomputed. BM25 does not yet run independently of the transformer; using the hash provider can only avoid model downloads temporarily, it is not research-grade dense |
| Query → dense/lexical | `retrievers.py:12–38,48–56,77–90` | Dense is a dot product after normalization in the existing adapters; BM25 is hand-written with k1=1.5/b=0.75, NFC/lowercase, unigrams+bigrams. Not BGE sparse. Ties follow the stable chunk order |
| Fusion → rerank | `retrievers.py:59–74,77–95` | Default pool 25; hybrid takes 50 per branch then unions/fuses down to 25; RRF has weights and rrf_k. Rerank is a local CE over query/chunk pairs, max_length=512; returns the whole ranked pool |
| Ranking → metrics | `run.py:72,79–107`; `metrics.py:6–42` | `k` only adds a recall cutoff and does **not** cut the ranking/context. The YAML `pool` is not passed in the call on line 81. Metrics cover answerable only; the refusal proxy uses the top score of both classes |
| Output | `run.py:91–94,110–130,134–155` | Writes only ID/config/top_score/metrics per question; no ranking, candidate IDs, context, prompt/output/citations. Written at the end of the whole run; an exception mid-loop loses the results still in RAM. `reference_answer` is not used |

`run.json` has the config, HEAD, chunk/question counts and Python/platform/processor (`run.py:115–123`), but no content hashes, dirty source identity, dependency/runtime versions, resolved revisions, RAM or step timings. `corpus_embed_s` measures the whole embedder/index build (model load, cache/BM25), not inference time alone; it is reused across configs with the same embedder (`run.py:61–66,106`).

Two CPU notes: the index dict keeps embedders/models/matrices until the end of the run (`run.py:57–66`), so adding two embeddings does not by itself run them sequentially and free RAM. `rerankers.setdefault(rk, CrossEncoder(...))` evaluates the constructor before calling setdefault (`run.py:70`), and may reload the model when the key already exists. This is code behaviour; peak RAM and latency were not measured.

### 2.2. Runtime Q&A and ingestion

The chat path's root: `services/ai-qa-service/src/main.py:67` includes the chat router; `src/api/routes/chat.py:21,42,91–112,156–179` creates a singleton `PipelineOrchestrator()` then calls `process` or `process_stream`.

In the table below, the prefix **AI** = `services/ai-qa-service/src/`, **ING** = `services/ingestion-service/src/`.

| Stage | Evidence | What was verified |
|---|---|---|
| Before retrieval | AI `services/pipeline/pipeline_orchestrator.py:164–213,349–420` | Toxic filter → intent; SIMPLE goes to a separate responder. COMPLEX calls the query refiner and searches with the refined query; with history. Unlike offline, which uses the original query, one turn |
| Query embedding | AI `services/retrieval/hybrid_search.py:17–41,63` | HTTP `/v1/embeddings`, model from settings, the raw query as input; no instruction/revision in the payload. Server tokenizer/max length not verified |
| Dense DB | AI `db/repositories/chunk_repo.py:47–88` | pgvector cosine distance + department boost, ACL/latest/published/expiry. Has a JOIN to metadata (drift from the guardrail forbidding cross-schema joins); not a design to copy |
| Lexical DB | AI `db/repositories/chunk_repo.py:95–183` | Named `bm25_search` but the SQL is `ts_rank`, weighted content/title/section, `plainto_tsquery('simple',...)`, department boost, normalized by the result maximum. No BM25 IDF/k1/b as in eval |
| Fusion/filter | AI `services/retrieval/hybrid_search.py:65–107,119–136` | Takes `limit*2` per branch; RRF k=60, weights 0.7/0.3 hardcoded; sorted by fused score but returns objects keeping the original similarity. For the same ID the vector object wins; lexical-only keeps the normalized lexical score. Similarity filter before rerank |
| Reranker injection | AI `services/pipeline/pipeline_orchestrator.py:40–80,234–238,439–442`; AI `api/routes/chat.py:42` | The constructor takes an optional reranker and assigns `self.reranker_service = reranker_service` directly, with no singleton fallback. Chat does not inject it, so it is `None`: `use_reranker=True` alone cannot enable this path |
| Reranker entity | AI `services/retrieval/reranker.py:11–61` | A singleton with an HTTP `/rerank`, truncate true; overwrites `similarity_score` with the CE score. Timeout/non-200/exception returns the old ranking. No record distinguishes a successful rerank from the fallback in artifacts |
| Gap/refusal | AI `services/knowledge_gap.py:32–62`; AI `services/pipeline/pipeline_orchestrator.py:240–265,310–320,444–488,531–540` | The gap compares the same threshold on `similarity_score`; marks/publishes unanswered. There is no branch that stops generation when gap=true: the prompt is still sent. The gap flag is not the same as an actual refusal |
| Prompt → SDK | AI `services/generation/prompt_builder.py:4–14,21–55`; AI `services/generation/llm_client.py:19–48,50–104,139–182` | The prompt asks for grounded answers in the query's language, citing titles; uses at most 10 chunks, each cut to 2500 characters. LLMClient resolves the profile then calls `AsyncOpenAI.chat.completions.create` directly; not through `ModelRegistry.generate` |
| Profile/fallback | AI `services/generation/model_registry.py:21–80,100–105`; AI `services/generation/llm_client.py:19–46,105–137,187–219` | The registry provides profile/model_name/base_url; the client has preemptive fallback and fallback when local fails. Profile/model names in code do not prove a provider is available or free |
| Ingestion → vectors | ING `services/pipeline.py:194–214,235–253,309–312`; ING `services/embedding_service.py:46–93,124–160` | ParentChildChunker → embed_batch_cached → persist. Cuts with cl100k_base at 512 tokens, 2000 characters on error; the payload model comes from settings but the cache/persist records a fixed BGE_M3/1024. The cache is looked up by text hash + a fixed model label; not enough to distinguish the real model/revision/preprocessing |

Settings are the on-disk defaults, not the deployed configuration: AI `config/settings.py:30–31,65–68` has embedding `jina-embeddings-v3`, retrieval_limit=25, rerank_limit=10, similarity_threshold=0.15, use_reranker=true. `.env` was not read to infer overrides.

**An additional static bug blocking system verification:** AI `services/pipeline/pipeline_orchestrator.py:275–276,449–450` imports `build_sources` from `src.api.routes.chat`, but the whole of `chat.py:1–180` neither defines nor imports this symbol. Reaching this point on a branch with chunks would raise an import error on this snapshot; the endpoint was not exercised over HTTP to confirm. Non-stream calls generation before the failure point, stream builds sources before generation. Not fixed in this session.

## 3. Handoff questions resolved

| Question | Evidence-backed conclusion | Limit / proposed minimal fix |
|---|---|---|
| ts_rank vs BM25 | Confirmed different algorithm, tokenizer/features, score scale and filter; §2 | Use offline BM25 for research, named clearly. Runtime parity is a separate gate before claiming the system uses the winning configuration; a DB BM25 is not required before research |
| The 512 cap | Eval ST forces `min(max_seq_length or 512,512)` (`embedders.py:44–56`); CE forces 512 (`retrievers.py:71`); ING cuts at 512 cl100k (`embedding_service.py:54–68`) | The three caps use different tokenizers. Do not infer the model only supports 512, nor how much evidence is lost. Parameterize max_length, record the tokenizer/truncation counts; workstream 03 chooses the policy, workstream 05 measures truncation tails |
| Instructions | Eval ST has only query_prefix; the API adapter ignores is_query (`embedders.py:53–78,115–117`); the runtime payload has no instruction | Needs query/document roles and the rendered input/template per model; do not apply one prefix to the whole shortlist. build_embedder does not forward batch_size even though the constructor takes it |
| Revision | Eval accepts a revision but the research config has none (`configs/rq1-rq3-bge-m3.yaml:5–13`); the name records unpinned when missing | Resolve/pin an immutable revision before official runs; tokenizers and the reranker need revisions too. `run.json` does not discover revisions itself, even though the YAML comment suggests looking at run.json |
| Cache | The eval ST namespace includes model@revision and the file text hash; not the effective max_length/tokenizer/code/precision/normalization; the API namespace has only the model (`embedders.py:51,66,81–107`) | Queries are not cached now; query_prefix does not make the corpus stale today since it only applies to queries. But query provenance is missing, and changing document preprocessing/caps can reuse wrongly. A new cache must key on a full input+adapter fingerprint |
| Reranker injection | Confirmed the chat default does not inject; eval has a real CE when rerank is configured and the adapter is created | Offline does not depend on runtime injection. Before integration, inject the singleton deliberately and test on/off/error; do not call the fallback a successful rerank-on |
| Score separation | Eval hybrid ranks by RRF but the tuple holds the dense score of the first selected chunk; rerank overwrites the tuple with the CE (`retrievers.py:88–94`). The runtime mixes dense/lexical scores then overwrites with CE | Store raw scores/ranks, the fused score, the CE score and the gate feature/value/stage separately. Do not treat the dense score at the fused top as the max dense; do not use a shared threshold across scorers/models |

## 4. Checking metrics and ranking depth

### 4.1. Code reading

`metrics.py:6–11` only compares doc/pages and returns the **first target** hit; every chunk on the same page/document counts as a hit even if it does not contain the answer span. With MD on page 1, document-level labels are especially coarse. `14–26` computes recall over the covered target set, MRR over the whole ranking passed in, while DCG adds **every hit chunk**; IDCG is based on the number of targets. The two relevance units are inconsistent.

The current pool of 25 can supply up to 10 positions for nDCG@10 if the corpus has enough candidates; **there is no evidence that nDCG always lacks depth 10 by default**. However the MRR named without a cutoff is in practice MRR@25 (or less with a small corpus); results do not reflect first hits outside the pool. `k>25` can still output recall@k from a 25-item list, without a warning. This is a labelling/depth validation error, separate from the DCG bug. Rerank only reorders within the pool and does not recover evidence outside it.

`run.py:47,79–107` has no split/tune/freeze; the sweep runs on the dataset passed in, which may be test. The sweep function describes a proxy and does not itself choose a threshold; choosing an operating point from it on test would leak. There is no answer-level correctness in `false_answer`.

### 4.2. Small executed evidence, no model/API

Used the available Python 3.12, `python -B -` from the repo root, `importlib.util.spec_from_file_location` loading **only** `eval/sopilot_eval/metrics.py`; with `SimpleNamespace(doc=...,page=1)`. No service/settings imported, no fixtures/tests/cache written. The results below verify the tooling, not research measurements.

| Reproducible input / operation | Actual result | Classification |
|---|---|---|
| `retrieval_metrics([a,a],[{'doc':'a'}])`, a being a chunk doc=a/page=1 | recall@10=1; **ndcg@10=1.6309297535714575** | Proven bug: DCG/IDCG in different units, above [0,1] |
| One a; expected containing doc=a and doc=a/pages=[1] | recall=0.5; nDCG=0.6131471927654584 | Confirms first-match hides the other target. Whether this is a labelling or scorer bug depends on the workstream 02–03 overlap contract, not decided here |
| 25 chunks x not hitting; the same list plus a at rank 26 | MRR goes from 0 to 1/26=0.038461538461538464 with the full ranking | Proves MRR depends on the input depth; the retrieval code currently returns only pool25 |
| `retrieval_metrics([],[])` | `ZeroDivisionError` | Proven robustness bug. run currently only calls metrics for answerable; answerable items without gold must be rejected at preflight, not every unanswerable crashes |
| `refusal_sweep([0.5],[0.5],steps=2)` | Three rows with the same threshold=.5, false_refusal=0, false_answer=1 | The sweep has no refuse-all point and does not resolve ties; needs sentinels at both ends and score boundaries |
| `refusal_sweep([0.5],[],steps=2)` | false_answer=0 even without unanswerable questions | An empty denominator is presented as 0 errors; needs null/N/A + counts |

The command reproducing the main bug, needing no dependencies beyond Python (from the root):

```powershell
@'
import importlib.util
from types import SimpleNamespace
s = importlib.util.spec_from_file_location('metrics', 'eval/sopilot_eval/metrics.py')
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
a = SimpleNamespace(doc='a', page=1)
assert m.retrieval_metrics([a, a], [{'doc': 'a'}])['ndcg@10'] > 1
'@ | python -B -
```

This assertion confirms the **current bug**; it is not the acceptance test after the fix. After the fix, nDCG must match the locked definition.

### 4.3. Minimal metric fix specification

1. Workstreams 02–03 lock the unit: evidence targets with durable IDs, spans/sections and acceptable chunks; distinguish several targets that are all required from several alternative positions for the same target. The scorer maps the ranking to the target set; arbitrary doc/page is not the final gold.
2. If **target coverage with binary gain** is chosen, gain is granted only the first time a target appears; repeated chunks hitting the same target add no gain. With one target per chunk, DCG and the ideal share the same unique target; `IDCG@k=sum(1/log2(r+1), r=1..min(k,n_targets))`. The name must say `target_nDCG@k`, not standard chunk nDCG, while there are no chunk qrels. Do not fix it by clamping nDCG to 1.
3. If one valid chunk covers several targets, the gain/ideal formula above cannot be applied as is (the gain could exceed 1). Workstreams 02–03 must settle a disjoint mapping or a coverage metric with a matching ideal; overlap fixtures must be rejected or scored by an explicit policy. If chunk-level nDCG is chosen, build chunk qrels and compute IDCG from those qrels, not from the number of evidence targets. Do not let implementation convenience substitute for a scientific choice.
4. Recall counts unique target coverage; add all-targets-found per the multi-evidence contract. MRR is named `MRR@D`, distinguishing candidate recall@pool from the context@k metric. Preflight requires depth >= the maximum cutoff to be reported; with a small corpus, record the effective depth rather than inventing results. Ties have a deterministic rule that is recorded.
5. The threshold sweep uses dev, a fixed score type/stage, with always-answer/refuse-all, ties, empty candidates => explicit refuse, and missing scores; no 0 sentinel for missing (CE can be negative). Freeze the threshold before test, store numerator/denominator/coverage; split by EN/VI and answerability, not only the aggregate.

Tests needed: duplicate chunks/targets; distinct targets; irrelevant at the top; a hit beyond the cutoff; ideal/all irrelevant/empty ranking; invalid empty expected; overlap/alternatives; ranking <k; ties and missing scores; metric domain [0,1]; reordering targets does not change the score when the policy allows. `eval/tests/test_eval.py:11–35` currently only has first hit/page constraint/RRF/proxy extremes/smoke files; it does not protect these cases. The full suite was not run in the survey session.

## 5. Parameterized contract with workstreams 02–03

This is a proposed schema for implementation, not an approved dataset/shortlist. Missing values must fail preflight for an official run, not silently take research defaults.

| Part | Minimum fields | To reconcile later |
|---|---|---|
| Corpus/chunks | corpus_version; doc_id/source_url/license/source_revision/raw_hash/extracted_hash/lang=en; chunk_id/doc_version/section/page/span/text_hash; extraction/chunking implementation+params | Workstream 02: sources, sharing rights, spans and the chunk-evidence map. Keep one shared chunk manifest for both embeddings |
| Query/gold | query_id/group_id/split/question/lang/en→en or vi→en/answerable; target IDs and alternative/required groups; reference_answer; gold_version/reviewer/status; answer_subset flag | Workstream 02: split by group/near-duplicates, human-reviewed labels, subset and negatives. Do not split same-meaning pairs across dev/test |
| Retrieval | retriever enum; embedding profiles E_A/E_B; lexical tokenizer/version/k1/b; dense_pool/lexical_pool/fused_pool; weights/rrf_k; metric_depth/context_k; tie_policy | Workstream 03: the two specific models, pool/k and comparison conditions. Independent BM25 runs once for the same corpus/config; do not duplicate it into two observations just because the embedding differs |
| Model adapter | provider/model/resolved_revision/tokenizer_revision; role-specific instruction/template; effective max lengths/truncation side; pooling/normalize/dim/dtype/device=cpu/batch/threads | Workstream 03: a policy per model; do not assume every model supports the same instruction. Client/server adapters must share the same effective contract if an embedding API is used |
| Rerank/gate | reranker profile R + revision; pair template/max length/batch; enabled; input candidate IDs; gate feature/stage/aggregation/threshold/dev_hash/freeze time | Workstream 03: the same pool on/off; a controlled gate comparison. Do not let enabling rerank also switch from cosine to CE without declaring it a separate condition |
| Answer | subset hash; generator G/model requested/actual/provider version; prompt version; context_k/token budget/output cap; temperature/top_p/seed if supported; history=[]; fallback policy; review rubric version | Workstreams 02–03: the subset/rubric and generation conditions. One fixed generator; API availability/quota checked at run time, no provider chosen here |

The result per candidate must contain `{query_id, chunk_id, dense_rank, dense_score, lexical_rank, lexical_score, fused_rank, fused_score, rerank_rank, rerank_score, selected_for_context}`; null when a branch is absent, without overwriting fields. A separate gate record `{feature, stage, value, threshold, accepted, reason}`. A hybrid top chunk may exist only in the lexical pool; if the gate needs its dense score, that feature must be defined/computed first, not substituted with the lexical score.

## 6. Answer level: what must be added

The current harness is retrieval-only even though it has reference_answer. The runtime has output/model/sources in conversations but cannot replace QA artifacts: prompts are not snapshotted, context is truncated, sources are mostly titles; the has_sources flag only depends on having chunks (`pipeline_orchestrator.py:271–276`) and does not prove the output cites correctly.

The proposed shortest path: add `eval/sopilot_eval/answer_run.py`, a `generation.py` adapter and `review.py`/an equivalent schema, reading locked ranking artifacts; run a single independent turn, without DB/history/refiner/intent/title generation. If the prompt formatter is reused, turn it into a pure function or adapter; do not import service singletons that pull in settings/API dependencies. This is a QA research path published separately, not claimed to be at parity with `/chat`.

Each `query × config × replicate` unit must store:

- The context actually sent: ordered chunk IDs, text snapshots, source version/span, truncated parts, token counts/budget and stable citation aliases like `[S1]` mapped to chunks. Keep the pre-context candidates too, to distinguish retrieval misses from context loss.
- The verbatim system/user messages, prompt/template hash, the original and effective query, model requested/actual/version, the generation parameters actually sent, response ID, usage/finish_reason and the raw + parsed output. Not only the title or output with tags removed.
- Gate accepted/refused separate from `observed_llm_refusal`; questions refused by the gate have the decision status and message, with no fake LLM output. Always-answer is an explicit baseline. If always-answer outputs are reused to simulate thresholds, the context/prompt/generator must stay the same and the gate must only block before generation; declare it a decision replay, with real generation latency and simulated policy latency separated.
- Citation mentions/claim spans → alias → chunk/span, invalid/unresolved citations; reviewer labels for correctness/completeness against the reference, faithfulness against the actual context, citation precision and completeness per claim, correct/incorrect refusal. Do not infer citation correctness from the alias existing. The rubric supports N/A with denominator=0, and does not reward refusals with default correctness/citation points.
- Review record: output_hash, rubric_version, reviewer_id, reviewed_at, per-claim labels, overall labels/reason, disagreement/adjudication/status. Hide config names from reviewers when feasible. A single reviewer must be recorded as a limitation; an optional LLM judge does not replace human gold.

RQ2 only has an answer-level conclusion with paired on/off on the same reviewed subset/generator/prompt/budget. RQ3 must have false refusals, false acceptances, coverage and real output errors among answered questions, including wrongly answered answerable ones; do not rename the retrieval proxy `false_answer` as a hallucination rate. Report EN/VI queries separately, the number of missing/failed samples, and do not count timeouts/API quota as refusals.

## 7. Run artifacts and resuming after quota runs out

Propose an immutable run directory with an ID based on a UUID/hash rather than a single-second timestamp (`run.py:51–53` may share a folder within the same second). The manifest is created **before** inference; every output has a schema version, run/config/query keys and a checksum.

| Proposed artifact | Content / reproduction keys |
|---|---|
| `manifest.json`, `resolved_config.json` | SHA-256 of the raw corpus + extracted manifest, the ordered chunk manifest, query/gold/subset/split; config canonical JSON hash; metric/rubric/prompt versions; HEAD + dirty flag + hashes of exactly the source/lock files used in the run. The repo is currently dirty/untracked so HEAD is not enough; store a snapshot of the selected code in the repo, excluding `.env`/secrets and other session files |
| `environment.json` | Python/OS/package versions, `uv.lock` hash, model/tokenizer resolved revisions or server deployment/version/fingerprint; CPU model/physical/logical cores, total/available RAM/peak RSS, device, thread counts, batch, dtype/backend/quantization, cold/warm cache, seed and time/timezone. Do not take the 32 GB total RAM as peak/available |
| `corpus_manifest.jsonl`, `chunks.jsonl`, `queries.jsonl` or hashed references | URL/license/source snapshot, IDs/spans/text/hashes, query groups/splits/gold version. Enough to rebuild the mapping; a hash does not replace data that may be stored/shared |
| `embeddings/`, cache manifest | SHA-256 key of the effective model+immutable revision+tokenizer+adapter/code+role+rendered input hash+max_length/truncation+pooling+normalize+dtype/dim/backend; batching/threads also recorded in provenance. A separate query cache with role=query; document cache with role=document. Validate shape/finite/dimension/checksum before reuse; write to a temp file then atomic rename |
| `rankings.jsonl`, `timings.jsonl` | Scores/ranks of every stage, pool/depth/context selection and gate. Separate model load, extract/chunk, corpus embedding/index build, query embedding, dense, lexical, fusion, rerank, context/prompt, API wait/TTFT/completion, parse/persist and total; unit ms, monotonic clock, cache hit/miss, warm/cold and sample count. Retries/backoff counted separately and in the wall total; do not mix cache hits into inference throughput |
| `answers.jsonl`, `reviews.jsonl` | The §6 records, joined by query/config/replicate/output hash. If the response model/version is missing, record unavailable rather than inventing a revision. If the API only has a mutable alias, lock the run window, keep the raw response metadata and publish the reproducibility limit; keep outputs so they can be regraded without calling the API |
| `tasks.jsonl`/checkpoint and `attempts.jsonl` | Stage/task key, status pending/running/succeeded/retryable_failed/permanent_failed/unknown, attempt ID, request hash/response ID, redacted HTTP status/error code, timeout, retry-after, backoff, timestamp/duration, output checksum. Never store auth headers, tokens/API keys or configs containing keys |
| `metrics.json`, `report.md` | Regenerated from rankings/answers/reviews without calling models; counts/denominators/missing and EN/VI/answerability cohorts; paired query/group IDs for workstream 05's analysis. Distinguish proxy, human-reviewed and system validation |

Checkpoints are not only at the end of a run. The generation task key = hash(run inputs + query + candidate/context order/text + prompt + model/version + generation params + replicate); skip only when succeeded and the output checksum matches. Flush each successful query/stage with an atomic per-task file or a journal with a completion record; after a crash drop an incomplete last JSONL line and never mark truncated output as successful. Persist rankings before the API so running out of quota does not require re-embedding/reranking.

Retry policy: limit the number of attempts/time, exponential backoff with jitter, honour `Retry-After` when present; on 429/quota checkpoint and pause scheduling, bounded retries on 5xx/network/timeout, clear failure on auth/schema errors. A timeout after the server received the request is an uncertain completion; record it as unknown/a separate attempt, without pretending to guarantee exactly-once. Use idempotency/request IDs if the provider supports them; if not, avoid unbounded retries and keep every attempt for audit.

Do not fall back to another model automatically when quota runs out. Changing the generator/version creates a new condition/run and reruns all affected paired cells, not mixed with the old run; only generation that needs changing is rerun, retrieval reused through checksums. Stochastic models/mutable APIs do not guarantee bit-for-bit output; artifacts allow exact reanalysis of stored outputs and reruns with provenance. Crash/resume/checkpoint tests use a fake API, without spending real quota.

## 8. Minimal fix order and acceptance criteria

This is a proposed technical order, **not a PLAN/ticket**, and does not update the progress source. A blocks the corresponding experiments; B blocks system claims; C can be deferred.

| Order | Expected files/scope | Dependencies | Tests and acceptance criterion |
|---|---|---|---|
| A1 — metric/gold/depth | `eval/sopilot_eval/{metrics,corpus,run}.py`, `eval/tests/test_eval.py`; a small added schema/preflight | The relevance/split contract from 02–03; synthetic fixtures usable right away | The §4 counterexamples are tested; nDCG has the right definition/domain, target duplicates/overlaps handled explicitly; wrong/insufficient-depth input rejected; MRR@D named correctly; no more fake-0 empty denominators |
| A2 — adapter/config/cache | `eval/sopilot_eval/{embedders,retrievers}.py`, `eval/configs/`, `eval/pyproject.toml`/lock if needed | The A1 schema; profiles E_A/E_B/R filled in by 03 before the official run | Mock encoder/API: correct query/doc instructions, max_length/batch/device actually forwarded; changing revision/cap/preprocessing invalidates the cache; dimension/finite checks. BM25 does not call the embedder; both models are not held in RAM; each reranker key is created only once |
| A3 — scores/pool/run records | `eval/sopilot_eval/{retrievers,run}.py`; add `artifacts.py`/equivalent; tests | A1–A2 | The config pool actually takes effect; candidate IDs identical on/off; scores not overwritten; context_k separate from metric depth; manifest/checkpoint written at the start of the run; exceptions keep completed queries; metrics recomputed without calling models |
| A4 — dev gate | `eval/sopilot_eval/{metrics,run}.py`, config/gate schema | A3 + a locked dev split/feature | Synthetic ties/negative/empty scores/classes; always-answer/refuse-all present; threshold from the dev artifact hash; the test runner only accepts a frozen threshold, no tuning on test; coverage/counts/N/A by class/language |
| A5 — QA subset + API checkpoint | Add `eval/sopilot_eval/{answer_run,generation,review}.py` and tests/schema/prompt | A3; the subset/gold/rubric from 02–03; A4 for refusal eval; the generator verified at run time | Fake API tests of input context/prompt/citation map/output/review join; crash after N questions then resume without recalling succeeded ones; 429/5xx/timeout/invalid citations/partial output; no silent fallback; changing the prompt/model creates a new task key |
| A6 — pilot then freeze | `eval/README.md`, resolved configs/run artifacts in the following implementation round | A1–A5 + a valid dataset/models | Synthetic smoke without downloads; a real-model CPU pilot only in an authorized run session, measuring RSS/latency/truncation/cache; lock data/config/threshold/subset before test. Run E_A then free it, then E_B, one reranker model; no promise that 32 GB is enough before the pilot |
| B1 — runtime wired correctly | AI `api/routes/chat.py`, `services/pipeline/pipeline_orchestrator.py`, `services/retrieval/reranker.py`, `services/generation/{prompt_builder,llm_client}.py`, tests | A standard harness exists; not needed before A1–A6 | Inject the reranker, fix the build_sources symbol; mock process/stream goes through retrieval→rerank→prompt→generation→sources/persist; on/off/error asserted explicitly; the actual max_tokens matches the config (the stream client currently hardcodes 2048 at line 171 despite taking an arg); the real model/fallback transparent |
| B2 — parity + isolation | AI retrieval/chunk repo/models; ING embedding/cache/chunker; the corresponding context if the contract changes | The chosen research configuration, schema/ownership review per AGENTS | The same corpus/chunks/model revision/instruction/scorer/gate; compare candidate IDs and scores with a predefined tolerance. Check tenant/ACL/latest/deleted/expiry and scope filters. The runtime does not pass the workspace into search in §2, and the SQL metadata JOIN still violates the guardrail; do not claim isolation from code reading alone. Migrations, if needed, must be additive per the repo rules, not created during the survey |
| C — deferred | A separate CPU serving setup, a BM25 DB extension, the RQ4 overhead/RLS benchmark, deployment, UI, extended OCR/DOCX, a third model, an automatic judge | Only if goals/resources call for it | Does not block offline research on validated MD/TXT/text PDFs; isolation is not dropped when publishing a multi-workspace system |

Test gate for later implementation: `eval` has its own suite (`eval/pyproject.toml:12–14`); `scripts/run-tests.ps1:3`/`validate-build.ps1:14–15` has no eval scope yet. Use the installed env interpreter and pytest from the eval folder, for example `.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q`; only after checking dependencies, without an auto-sync that may download in the survey session. If the runtime is changed later, run targeted unit tests and `validate-build.ps1 -Scope ai-qa`/`ingestion` for the parts touched, plus the pre-commit gate. Do not treat pre-commit as covering eval; this docs session did not run the full gates for other people's changes.

## 9. Final gap table and handoff checklist

| Gap | Main evidence | Priority / closing condition |
|---|---|---|
| nDCG >1; page/doc gold too coarse; overlapping first-match | `metrics.py:6–26`, counterexamples in §4.2 | **A1 blocks research metrics**; relevance contract and regression tests pass |
| Pool/k/depth and gate not separated | `retrievers.py:77–95`; `run.py:72,81–107` | **A3–A4 block correct ablation/refusal**; explicit pool/depth/score feature, dev freeze |
| Embedding cap/instruction/revision/cache insufficient | `embedders.py:44–56,63–78,84–117`; config `rq1-rq3-bge-m3.yaml:5–13` | **A2 blocks reproducible comparison of two embeddings**; effective adapter/provenance + cache invalidation |
| Runtime lexical differs from eval, mixed scores and prefiltering | AI `chunk_repo.py:135–180`; `hybrid_search.py:95–107,119–136` | **B2 blocks parity**; does not block offline BM25 if the algorithm and limits are stated |
| Reranker not wired by default; build_sources missing | AI `chat.py:42`; orchestrator `80,235,275,439,449` | **B1 blocks system validation**; mock + integration smoke when authorized |
| QA/citation/refusal outputs not in eval | `run.py:91–130`; runtime prompt `4–14,45–53`; gap `32–62` | **A5 blocks answer-level RQ2–3**; artifacts and human review, no retrieval proxy in place of QA |
| Metadata/checkpoint/step timings missing | `run.py:51–58,79–82,110–129`; `embedders.py:93–94` | **A3/A5 block long/quota-bound API runs**; resume/recompute tested with fake adapters |
| Real RAM/throughput/model/API not measured | `run.py:57–70`; machine fields `121–123` are only raw metadata | **A6 gates the official run**; CPU/RSS/latency/quota pilot later; no winning-model conclusion |
| ACL/workspace/schema parity not verified | AI `chunk_repo.py:51–67,142–156`; orchestrator `225–231` | **B2 before system claims**; isolation tests, boundaries fixed properly; RQ4 overhead still deferred |

**The shortest implementation order:** lock the contract with 02–03 → fix metrics/preflight → adapters/cache and independent BM25 → rankings/scores/manifest/checkpoint → dev gate → generation subset + review → CPU/API pilot then freeze → official test. Do runtime injection/sources/parity/isolation later or independently; they must be finished before claiming system integration, without pulling the full stack into the offline harness.

Experiment readiness checklist (status at handoff):

- [x] Traced eval and runtime on disk; verified the questions, recorded file/lines; reproduced the metric bugs with plain Python.
- [x] Separated proven bugs, static behaviour, open contracts and measurements not done; only the workstream 04 file was written.
- [ ] Workstream 02 hands over a valid EN corpus snapshot, EN/VI queries with groups/splits/gold/reviewers and a subset hash.
- [ ] Workstream 03 fills in E_A/E_B/R, instructions/tokenizers/caps, pool/k/metric/gate/rubric and the freeze rules; no implicit defaults left.
- [ ] A1–A4 fixed and synthetic tests pass; metric domain/depth correct, BM25 independent, cache identity sufficient and raw rankings stored.
- [ ] A5 has a QA runner, citation map, human review labels; fake API crash/quota/resume pass, secret redaction verifiable.
- [ ] A6 CPU pilot of RAM/latency/truncation, generator/quota verified at run time; environment/inputs/code/config hashed with revisions.
- [ ] The test split/config/threshold/subset frozen; workstream 05 recomputes metrics/reviews from artifacts without calling models/APIs.
- [ ] B1–B2 pass before system conclusions; if not, the report states clearly that results are from the offline/QA harness, with the integration limits.
