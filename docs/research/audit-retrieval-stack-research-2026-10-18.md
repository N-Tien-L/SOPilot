---
id: AUDIT-retrieval-stack-research-2026-10-18
title: "Research on choosing the embedding, hybrid retrieval and reranker for SOPilot"
status: final
type: audit
scope: retrieval
verdict: conditional-recommendation
created: 2026-10-18
updated: 2026-11-13
author: "Owner"
refs:
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/product/prd-v2-sopilot-mvp.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. Provider and deployment assumptions are as of 2026-10-18; ADR-006 §4.4 records the later decisions (local only, self-hosted Modal models since 2026-11-01).

# Retrieval stack research conclusions

Sources checked on: **18/10/2026**. This is a research recommendation, not ADR/PRD approval, performance acceptance or an implementation requirement. No model was run, no weights downloaded, no keyed API called and `.env` was not read in this research.

## 1. Selection conclusions

**BGE-M3 is still worth using, but there is no longer enough basis to make it the default best choice.** Keep `BAAI/bge-m3` as the reproducible baseline; promote `Qwen/Qwen3-Embedding-0.6B` to the highest-priority challenger. Both currently have a Cloudflare Workers AI deployment path at the same published unit price. The embedding and reranker need not come from the same model family.

| Environment | Proposed stack | Conditions |
|---|---|---|
| CPU research | BGE-M3 dense + BM25 + RRF; BGE reranker v2 M3 on/off; Qwen3-Embedding-0.6B and E5 instruct as controls | Pin revisions, use the right instructions, measure CPU/RAM/time; rerank may run on a fixed subset |
| Low-traffic free demo | Cloudflare BGE-M3 as the interim deployment baseline + pgvector + BM25/RRF + Pinecone `bge-reranker-v2-m3` → top 5 | At most 500 reranks/month system-wide on Starter; check p95 before claiming the NFR is met |
| Embedding choice after eval | Switch to Cloudflare Qwen3-Embedding-0.6B if it wins on VI/EN and cross-lingual SOPs at an acceptable CPU cost | Build a new index, re-embed the whole corpus, re-measure the refusal threshold; never mix vectors even at the same 1024 dimensions |
| Beyond the demo quota | Paid managed rerank, or the BGE reranker on Modal serverless GPU | Requires a budget or accepting credits/cold starts; 0 USD with every turn succeeding cannot be committed yet |

If **rerank must succeed on every turn**, 0 USD/month is only feasible within the quota: once it runs out, new turns must be blocked or wait for the reset. If continuous answering has priority, the hybrid order may be used on failure but the degraded state must be recorded; that turn must not be called reranked. There is no evidence for an unlimited, always-available free API guaranteeing p95 under one second.

## 2. The project's real constraints

[PRD-V2](../product/prd-v2-sopilot-mvp.md) requires VI/EN and cross-lingual, the owner's CPU without a GPU for eval, a 0 USD/month target and warm TTFT p95 < 3 seconds. FR-10 currently says rerank is optional and off by default for the free deployment. The new wish for always-on rerank needs to be reflected in the PRD/ADR/TECH when implemented; this report does not change that contract itself.

[ADR-006](../architecture/decisions/adr-006-free-tier-providers-and-environments.md) is still `draft`. The original reasons for choosing BGE were multilingual support, self-hosting, eval independent of quotas and a Cloudflare deployment. These are feasibility and reproducibility, not proof of being best on SOP data.

The [eval config](../../eval/configs/rq1-rq3-bge-m3.yaml) has BGE-M3 and the BGE reranker v2 M3 but does not pin revisions yet. The [embedders](../../eval/sopilot_eval/embedders.py) limit every SentenceTransformer to 512 tokens; the [retrievers](../../eval/sopilot_eval/retrievers.py) use a default pool of 25 and a cross-encoder max_length of 512. A chunk size of 800 in the YAML does not mean 800 model tokens. So the maximum context on the model card cannot be used to describe the length actually evaluated. `eval/configs/` currently has only smoke and RQ1–RQ3; no finished RQ5 Qwen/E5 configuration yet.

The stack above is a **proposed target**, not an integrated runtime. One important difference: the [runtime `bm25_search`](../../services/ai-qa-service/src/db/repositories/chunk_repo.py) runs PostgreSQL `ts_rank` with `plainto_tsquery('simple', ...)`, while eval uses a hand-written BM25 with unigrams+bigrams. The function name does not prove the runtime is BM25; the lexical scorer must be unified, or the two variants reported separately, before eval results are taken as representative of the deployment.

## 3. Model assessment

### Embedding

| Model | Exact source | Assessment for SOPilot |
|---|---|---|
| `BAAI/bge-m3` | MIT; >100 languages; 1024-dimension dense; 8192 model context; dense/sparse/multi-vector; queries need no instruction. [BAAI model card](https://huggingface.co/BAAI/bge-m3) | A reasonable baseline with clear local/cloud paths. The current hybrid uses a separate BM25; the model's sparse/ColBERT abilities should not be counted as a benefit already exploited |
| `Qwen/Qwen3-Embedding-0.6B` | Apache-2.0; 0.6B, >100 languages, 32K model context, 32–1024-dimension output; the query instruction affects quality. [Qwen model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | The priority challenger: small enough for the CPU test and also on Cloudflare; 0.6B is not evidence of faster CPU inference than BGE |
| `intfloat/multilingual-e5-large-instruct` | MIT; 1024 dimensions; about 0.6B; at most 512 tokens; queries need a task instruction, documents do not. [E5 model card](https://huggingface.co/intfloat/multilingual-e5-large-instruct) | A good control for RQ5, no reason to replace the deployment baseline right away; control truncation/instructions so the comparison is fair |

Qwen publishes a multilingual MTEB table with retrieval: Qwen3-0.6B **64.64**, E5 instruct **57.12**, BGE-M3 **54.60**; the table uses the leaderboard snapshot of **24/05/2025**. This is the authors' evidence for the challenger, not the latest ranking, a CPU benchmark or a Vietnamese SOP result. [Qwen's table](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B#evaluation)

[VN-MTEB v1](https://arxiv.org/html/2507.21500v1) records retrieval BGE-M3 **39.84**, E5 instruct **40.88**; the benchmark has much translated data and Qwen3 is not in the compared table. Do not infer that E5 certainly wins on SOPs/cross-lingual, and do not use VN-MTEB to claim Qwen3 is better without that measurement.

### Reranker

`BAAI/bge-reranker-v2-m3` is Apache-2.0, a multilingual cross-encoder scoring each query–passage pair; it differs from the embedding in both role and license. BAAI recommends it among the multilingual/efficient options, but "lightweight/fast" on the model card is not a commitment of 25 pairs at p95 < 800 ms on the owner's CPU. [Reranker model card](https://huggingface.co/BAAI/bge-reranker-v2-m3)

**Keeping this model for RQ2 and the managed demo is reasonable.** Do not make it local CPU inference on a low-RAM free service before measuring. There is no need to move to Qwen3-Reranker just because the embedding moves to Qwen: the two steps are independent, and replacing the reranker also changes the score distribution and requires recalibrating refusal.

BAAI says `bge-reranker-base` targets Chinese/English, while v2 M3 is multilingual. That is the reason not to prefer base for VI; the ADR's "weak in Vietnamese" remains an unmeasured hypothesis, not a verified SOP result. [BAAI list](https://huggingface.co/BAAI/bge-reranker-v2-m3#model-list)

## 4. Cloudflare and source conflicts to resolve

Workers AI has **10,000 neurons/day**, reset at **00:00 UTC = 07:00 Bangkok/Vietnam**. On the Free plan, exceeding the quota returns errors; beyond the free amount on Paid, charges apply. The pricing table currently lists BGE-M3 and Qwen3-Embedding-0.6B at the same **1075 neurons/million input tokens**; in theory about **9.3 million tokens/day** if the quota is used only for embedding, not a fixed token quota or a guaranteed number of questions. [Official pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)

The hosted Qwen model uses ID `@cf/qwen/qwen3-embedding-0.6b`, with a serving context of **8192** instead of the 32K on the original model card. The API has query/documents fields and an instruction; local/cloud parity must be checked on a sample before local results are taken as representative of the deployment. [Cloudflare Qwen](https://developers.cloudflare.com/workers-ai/models/qwen3-embedding-0.6b/)

**Source conflict:** the Cloudflare `@cf/baai/bge-m3` page says **60,000 tokens**, its example uses `text` but the displayed schema shows `contexts/query`; BAAI describes the model as 8192. Do not settle on 60K or guess the real body from a contradictory page. Keep chunks short and check the real API contract, dimensions, normalization and local/cloud quality separately. [Cloudflare BGE](https://developers.cloudflare.com/workers-ai/models/bge-m3/), [BAAI original](https://huggingface.co/BAAI/bge-m3)

## 5. Managed rerank and recurring quotas

| Option | Verified from official sources | Conclusion |
|---|---|---|
| Pinecone Starter | BGE reranker v2 M3 **500 requests/month**, the only reranking model on Starter; the docs have a standalone `inference.rerank()`. [Pricing](https://www.pinecone.io/pricing/), [model/API](https://docs.pinecone.io/models/bge-reranker-v2-m3) | Matches the research model and the monthly quota. Postgres/pgvector stays; no vector DB switch. Latency from the backend region not measured |
| Cohere evaluation | **1000 API calls/month** shared; rerank **10 requests/minute**. Production uses a paid key. [Limits](https://docs.cohere.com/v2/docs/rate-limits), [going live](https://docs.cohere.com/v2/docs/going-live) | Good for evaluation; the trial is not a default free production option |
| Cohere `rerank-v4.0-fast` | Multilingual, includes VI; "fast" does not guarantee the project's latency. [Rerank overview](https://docs.cohere.com/v2/docs/rerank-overview) | An API challenger if the cost/production key is accepted after eval |
| Modal Starter | **$30 compute credit/month**, self-hosted CPU/GPU. [Pricing](https://modal.com/pricing) | Model autonomy, but compute credit does not translate directly into a number of turns; an always-warm GPU consumes credit, scale-to-zero has cold starts |

Modal has a workspace usage budget before credits and a spend limit for payment after credits; the docs say workloads causing extra charges stop when the spend limit is reached. Do not treat the default budget as a free guarantee: for example, $100 of usage and $30 of credits creates a default spend of $70. Check the dashboard values before deploying. [Modal budgets](https://modal.com/docs/guide/budgets)

500 turns/month is only **about 16 turns/day** spread over 30 days, system-wide. FR-09 gives each user 50 questions/day, so one user could exhaust a month's quota in 10 days. A shared monthly limit, a daily limit and abuse protection are needed; do not add up several trial keys to dodge the limit.

The initial Voyage/Jina quotas discussed are not a basis for recurring free operation. This report prefers Pinecone's monthly and Cloudflare's daily quotas over sign-up gifts as a long-term assumption.

## 6. Measurements for the final decision

Do not use the CPU ranges of "3–15 seconds" once discussed as a benchmark: there are no measurements on the owner's machine, the real corpus, or a specific batch/thread/runtime. Likewise **p95 ≤ 800 ms** is a proposed budget for the rerank step alone, not a proven speed or a requirement from the docs; the PRD only has warm TTFT p95 < 3 s.

1. **Settle the data:** VI→VI, EN→EN, VI→EN, EN→VI and unanswerable questions; human-reviewed relevance labels, a validation/test split, the same corpus/chunks for the three embeddings.
2. **Embedding:** BGE-M3, Qwen3-0.6B, E5 instruct with the right query instructions; pin the commit, tokenizer, pooling/normalization, max length, runtime. Record the truncation level, CPU model, threads, peak RAM, corpus embedding time and query p50/p95. A shared 512-token configuration is the first control; long context is a separate test.
3. **Retrieval:** dense, BM25, hybrid RRF. Measure recall@5/@25, nDCG@10, MRR and split the four language directions. Do not let an overall mean hide weak cross-lingual results.
4. **Rerank:** the same fixed candidates, local BGE vs Pinecone BGE on a fixed subset; pools 10/15/25, top 5, with/without rerank. Measure the full request time including tokenization/HTTP/queue, cold and warm separately; concurrency 1, then the expected demo level. Add Cohere only if the quota/conditions allow.
5. **Decide:** prioritize meeting the PRD's recall/citation/refusal and warm TTFT p95; choose the model from the quality–latency–RAM–quota frontier. If Qwen is better on VI/cross-lingual and operationally acceptable, switch the index; if the gain is small or CPU is too slow, keep BGE. Record the uncertainty from the small sample; do not claim an absolute winner.
6. **Settle operations:** a clear rerank timeout and quota policy; bounded retries so quota is not multiplied. Separate metadata `retrieval_score`, `rerank_score`, `rerank_status`, provider/model/version; do not reuse the same threshold for dense/RRF/cross-encoder/API scores. A separate end-to-end deployment eval; local scores are not the same as hosted scores.

Gates for opening a demo with rerank: the hosted contract works; lexical parity is checked or the difference recorded; the corpus/index has its own provenance; a system-wide quota protects the 500/month; timeout/degraded versus strict is decided; warm end-to-end TTFT meets the target under demo load; citation/refusal/tenant isolation have evidence. If any gate is not met, record that gate as unverified; do not turn research conclusions into acceptance.

## 7. Verification scope and work not done

Read the PRD/ADR/eval code/config and the author/provider pages cited at each point. Only this report was created; no code, schema, PRD, ADR or ticket progress changed; no stack started, no model inference and no benchmark. The measurements and hosted API contracts in §6 remain acceptance gates before implementation. `status: final` means the source research round is finished, not that the system meets quality/latency targets or has owner approval.
