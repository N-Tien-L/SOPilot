---
id: ADR-006
title: "V2: free AI/infrastructure providers; a local eval environment and deployment options"
status: approved
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
deciders: ["Owner"]
amends: [ADR-004]
supersedes: []
superseded_by: ""
---

# ADR-006: Free providers; eval on the local machine and deployment options

> **Status:** `approved` (2026-10-20) | **Proposed:** `2026-10-17` | **Decider:** `Owner`
>
> This ADR extends ADR-004 in two ways: the choice of embedding, LLM, reranker and storage, and how each environment runs. Evidence and analysis are in [AUDIT-v2-baseline-analysis](../../04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md).
>
> **Every free-tier figure below was read on 2026-10-17 and changes quickly.** Re-check them with the list in §6 before any deployment.
>
> Translated from Vietnamese on 2026-11-13. Section numbers and the numbered items of §4.1 are stable (code cites §4.1.2, §4.4).

---

## 1. Context and the decision to make
- PRD-V2 targets 0 USD/month. The project has two different outputs:
  1. **Research report:** eval must run many times, reproducibly, without being blocked by quotas.
  2. **CV:** a public deployment where others can sign in and try it.
- These need two different environments. With one shared configuration, either eval hits quotas or the deployment cannot run on a free tier.
- The old choices no longer work (AUDIT §4, §6):
  - Jina: a one-time quota.
  - Groq: most of the models in use have been shut down.
  - MinIO community: archived.
  - Hugging Face Spaces: creating a Space with compute now requires payment.
  - Oracle: the owner does not want to use it.

## 2. Evaluation criteria
1. 0 USD cost, preferring quotas that **refill daily or monthly** over one-time quotas.
2. Reproducible eval results: models and versions must be pinnable.
3. Switching provider through environment variables only, without code changes.
4. Low setup time and little risk of "lots of effort and it does not run".
5. Multilingual support (at least VI and EN, including cross-lingual).
6. **Feasible on the owner's machine (CPU, no GPU)**: prefer configurations that run and can be measured over the theoretically best ones. Every heavy option needs a reduced fallback (a subset, a smaller model), and its measured cost goes into the report.

## 3. Options considered (summary)

| Area | Option | Conclusion |
|---|---|---|
| Embedding | Jina API | Rejected: one-time quota, non-commercial use only |
| | Voyage API | Rejected: also a one-time quota |
| | Gemini embedding API | Backup only: data sent on the free tier may be used by Google to improve its products |
| | **bge-m3, run locally + called through Cloudflare Workers AI** | **Chosen:** MIT, multilingual, the same model in both environments |
| | Qwen3-Embedding-0.6B, multilingual-e5-large-instruct | Included in eval for comparison (RQ5) |
| Rerank | `bge-reranker-v2-m3` run locally | **Chosen for eval** |
| | Workers AI `bge-reranker-base` | Rejected: weak on Vietnamese (not measured on the project corpus) |
| LLM | Groq (old Llama models) | Rejected: shut down |
| | **Gemini Flash-Lite 3.x + Groq `gpt-oss-*`** | **Chosen for deployment** |
| | Local LLM (Ollama or llama.cpp) | **Optional for eval**, if the machine has enough GPU/RAM |
| Hosting models on a Hugging Face Space | — | Rejected: needs the PRO plan; a Space cannot reach Postgres |
| Hosting on Oracle Always Free | — | Rejected by owner decision |
| Object storage | **Cloudflare R2** (backup **Backblaze B2**) | Chosen for deployment |
| | Pinned MinIO version, or SeaweedFS | Chosen for local |

## 4. Decision

### 4.1 General principles (all environments)
1. **Every provider sits behind an interface.** ai-service has `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`), `RerankProvider` (`local` | `none`) and `LLMProvider` (OpenAI-style API: Gemini, Groq or a local server). The provider is chosen through environment variables.
2. **There is exactly one model configuration file** (`ai-service/config/models.yaml` or equivalent). Each task (`guard`, `generate`, `small_task`, `judge`) declares a provider, a model id and a list of fallback models. No model id is hard-coded. At startup the service calls the provider's `/models` and warns if a model has been removed.
3. **Embedding provenance is recorded.** Each chunk stores `embedding_provider`, `embedding_model`, `embedding_dim` and `embedding_revision`. Vectors from two different sources are never mixed in one index. The cache key is `(model, revision, sha256(chunk))`.
4. **Object storage uses only the standard S3 API.** Endpoint, bucket and key are configured through environment variables.

### 4.2 Environment A: eval for the research report (on the local machine)

**Goal:** runs many times, independent of quotas, reproducible results.

| Component | Choice | Notes |
|---|---|---|
| Infrastructure | `docker compose` with Postgres 16 + pgvector and a pinned MinIO version (or SeaweedFS) | No port opened to the Internet |
| Embedding | `BAAI/bge-m3` run locally through the CPU Text Embeddings Inference container, or sentence-transformers | Pin the model's commit hash on Hugging Face |
| Comparison models | `Qwen/Qwen3-Embedding-0.6B`, `intfloat/multilingual-e5-large-instruct` | multilingual-e5 reads only 512 tokens; chunks must fit |
| Rerank | `BAAI/bge-reranker-v2-m3` run locally | On or off per experiment configuration |
| Answer LLM | A small open-source model self-hosted on Modal (vLLM), chosen in §4.4 | Record the model with revision, temperature (`temperature=0`), seed, GPU type and cost |
| Judge LLM (faithfulness) | One fixed model, from a different family than the generator, for every run (§4.4) | Uses Modal budget, so it runs only on a fixed-size subset |

**Experiment design:**
- **Two measurement layers:**
  - Retrieval (Recall@k, nDCG@10, MRR, latency p50/p95): needs no LLM, so it can run any number of times.
  - Answers (citation precision, faithfulness, correct refusal rate): needs an LLM, so it runs less often.
- **Configuration matrix:**

  | RQ | Variable | Levels |
  |---|---|---|
  | RQ1 | Retrieval method | dense, BM25, hybrid (RRF) |
  | RQ2 | Rerank | off, `bge-reranker-v2-m3`; chunks in the prompt k ∈ {5, 10} |
  | RQ3 | Refusal threshold | sweep the threshold, plot the trade-off between wrong answers and wrong refusals |
  | RQ4 | Tenant filtering | application filter only, application filter + RLS (measure latency) |
  | RQ5 (proposed) | Embedding model | bge-m3, Qwen3-Embedding-0.6B, multilingual-e5-large-instruct |
- **Dataset:**
  - Public SOP documents and texts in Vietnamese and English, with source and license recorded. Each question has a language label (`lang`); cross-lingual questions (question and document in different languages) are flagged so the report can separate them.
  - Questions carry the expected document and page, an `answerable` flag, and a share of unanswerable questions.
  - An LLM may draft questions, but **a person must review them**. The report describes this process.
- **Reproducibility:**
  - Every run writes a `run.json` with the git commit, configuration hash, models with revisions, dataset size, timing and hardware.
  - The corpus is embedded once and reused for every retrieval configuration.
  - Results are stored in `eval/results/<run_id>/`. The summary report goes in `docs/research/`.
- **Hardware:** not yet measured on the owner's machine. The first run must record CPU/GPU/RAM and the time to embed the whole corpus for the report.

### 4.3 Environment B: public deployment for the CV

**Goal:** a recruiter or assessor signs in with Google and asks questions over demo documents, at 0 USD.

#### Option B1 (proposed): combine free services, no VM

| Component | Service | Free tier (2026-10) | Notes |
|---|---|---|---|
| Frontend | Vercel or Cloudflare Pages | — | Rewrite `/api/**` → core-api, `/ai/**` → ai-service so the browser sees one origin |
| core-api | Render Free (Docker) | 512 MB RAM, 0.1 vCPU, sleeps after 15 minutes | Tight for the JVM: use `-Xmx300m -XX:+UseSerialGC`, or a GraalVM native build |
| ai-service | Render Free (Docker) | Same | **Run no model inside this service** |
| Postgres + pgvector | Neon Free | 0.5 GB, 100 CU-hours per project, suspends after 5 idle minutes | A 1024-dimension vector takes about 4 KB, so a few tens of thousands of chunks fit |
| Object storage | Cloudflare R2 (backup Backblaze B2) | 10 GB | R2 may require a card or PayPal to activate |
| Embedding | Cloudflare Workers AI `@cf/baai/bge-m3` | 10 thousand neurons/day (about 9 million tokens, own estimate), refilled at 00:00 UTC | Errors when exhausted, never bills automatically. **Run no LLM on Workers AI**, since it shares the neuron quota |
| Rerank | Off | — | Re-enable when eval proves a benefit and there is somewhere to run it |
| Answer LLM | Gemini Flash-Lite 3.x | About 500–1,500 requests/day depending on the source | Free-tier data may be used to improve products; the free tier does not serve users in the EU, EEA, UK or Switzerland |
| Backup LLM and small tasks | Groq `openai/gpt-oss-120b` / `gpt-oss-20b` | About 1 thousand requests and 200 thousand tokens per day (Developer plan table) | — |
| Guard | Groq `meta-llama/llama-prompt-guard-2-86m` | 14.4 thousand requests/day | Dropped for V2 after the 2026-10-20 test (§4.4); this row is only historical for the deployment option |
| CI | GitHub Actions | Free for public repos | Runs the FR-19 tests |

> **Changed 2026-11-01:** the two LLM rows of B1 (Gemini, Groq `gpt-oss-120b`) are the original 2026-10-17 choice and are no longer the choice for answer generation; see §4.4. A deployment using models on Modal would have to account for cold starts and the $30/month limit; this has not been checked for public serving.

### 4.4 LLM roles for V2 (owner decision 2026-10-19; changed 2026-11-01)

> **Changed 2026-11-01 (owner, V2-02):** the 2026-10-19 version used Gemini and Groq `gpt-oss-120b` for answers and the judge, based on free-tier quotas. The owner switched to **small open-source models self-hosted on Modal**, to show the system does not depend on large commercial models. The guard, metadata suggestion, embedding and rerank rows are unchanged. Quota history and trial-call results are in AUDIT-v2 §4.1.

**Infrastructure for the two tasks that need a strong LLM (answers, judge):** Modal Starter plan, two accounts, each with $30 of compute per month (read at `modal.com/pricing` on 2026-11-01; **the terms on multiple accounts have not been checked**). Per-second pricing, converted to hourly: T4 $0.59, L4 $0.80, A10 $1.10, L40S $1.95, A100 40 GB $2.10; CPU $0.047/core-hour, RAM $0.008/GiB-hour, plus about $0.22/hour for a 2-core 16 GiB GPU container (estimate). Avoid region pinning (×1.15–1.75) and non-preemptible mode (×3). Do not use Modal's shared endpoints (billed per token, outside the $30). Run an OpenAI-compatible server (vLLM) behind `LLMProvider`, scaled to zero when idle, with weights cached in a Volume. Running 24/7 is not feasible (one L4 is about $576/month), so it is used for batch eval and for demos warmed up in advance.

| Task | Primary model | Fallback | Reason |
|---|---|---|---|
| Answer generation | **Qwen 3.5 9B**, quantized Q4 or FP8, on A10 or L4 (24 GB) | **Qwen 3.5 4B** on L4 or T4 if 9B misses the latency or budget | The Qwen family is the most recommended for Vietnamese at this size; the 256K context is ample for 3–5K-token RAG prompts; 9B fits in 24 GB. **Not yet measured on the project's SOP set** (see the selection criteria below) |
| Injection/jailbreak guard | Four layers with no LLM call (PRD FR-13): two-level input rules, prompt assembly with data tags, an output canary token check, logging | — | Llama Prompt Guard 2 86M was dropped after the V2-02 test (2026-10-20): it blocked 4/20 Vietnamese attacks correctly, wrongly blocked 2/10 easily confused English sentences and 1/10 document chunks. Read access is already enforced in SQL, so the guard is only a secondary layer |
| Metadata suggestions | Groq `qwen/qwen3.8-27b` (default `llm.suggest` in `models.yaml`, 30 RPM, 60K TPM as configured), owner chose Groq on 2026-11-11 | Rule results only | Short prompts. This is the only remaining Groq dependency; to drop it, switch to the generation model above or use rules only |
| Faithfulness judge | **Gemma 4** (a different family from Qwen, so it does not grade itself): the 26B MoE on L40S (48 GB) for the final run; E4B on A10 for trial runs during development | Shrink the graded subset, plus a fixed sample graded by hand | Different family from the generator. A small judge is weaker than `gpt-oss-120b`, so the report must say so and add 30–50 hand-graded questions for comparison. The Gemma 4 variant names and sizes have not been checked on Ollama/Hugging Face (sources conflict); confirm the tag before pulling |
| Embedding, rerank | Embedding: local (`bge-m3`). Rerank: `bge-reranker-v2-m3` locally on CPU or **on the A10 GPU in the same container as vLLM** (V2-35, owner choice 2026-11-09) | Local rerank | Independent of quotas. CPU rerank takes 15.7–18.1 s per question; sharing the GPU container adds no GPU and no separate cold start. Chunks sent to Modal are the same as those in the prompt. Two URLs on one container: `sopilot-vllm-serve` (chat) and `sopilot-vllm-rerank` (`POST /v1/rerank`) |

> **Note V2-25 (2026-11-12): the owner confirmed Groq for metadata suggestions, for this task only (not for answers or the judge).** Metadata suggestions (V2-25) send **excerpts of document content** (title, heading outline and at most a few representative passages, cut at a configured token ceiling) to **Groq**. This changes the data flow to an external provider, unlike Modal (self-hosted models); use only documents the owner accepts sending out. The model comes from `services/ai-service/config/models.yaml` (`llm.suggest`); the table above matches the `models.yaml` default (`qwen/qwen3.8-27b`, present on Groq's model page on 2026-11-12). Confirmed on 2026-11-12: `GET /models` with a real key returned 200 and listed `qwen/qwen3.8-27b`; a real run produced `method=LLM`, `llm_ms=2135`. The limits (30 RPM, 60K TPM) are still configured values, not checked against `console.groq.com/settings/limits`. Rules: rules first (title, document code, dates), one LLM call with a 20 s timeout, at most one retry; on failure store the rule results with `method = RULES_FALLBACK`. Results apply only to fields not set by the user.

**Answer model and replacement candidates (owner decision 2026-11-04, V2-10):** the owner dropped the full bake-off below and chose **Qwen3.5-9B, FP8, vLLM on L4** (A10 if L4 is too slow). Only one quick check before committing: about 20 questions from `sop-main` (including negatives), `temperature=0`, read by eye for answers in the question's language with `[n]` pointing to the right source, TTFT measured once cold and once warm, and output tokens compared with the displayed answer length to see whether `enable_thinking=false` really stops reasoning output. Expected cost $1–3.

Facts checked on 2026-11-04 (secondary sources, the official model card not yet read; open Hugging Face to confirm before pulling): Qwen3.5-9B is a dense 9B model, Apache 2.0, context about 262K, BF16 about 19.3 GB (so use FP8 on a 24 GB L4); vLLM has an official recipe; run with `--default-chat-template-kwargs '{"enable_thinking": false}'`; sources disagree on whether this flag stops reasoning or only hides the tokens. **There are no comparative Vietnamese measurements between the candidates**; choosing Qwen3.5-9B is a reasonable hypothesis, not a measured result.

Replacement candidates, in the order to try when problems appear (switched only through `models.yaml`/`LLMProvider` environment variables, without pipeline changes):

| Symptom in real runs | Switch to | Modal GPU | Notes and open checks |
|---|---|---|---|
| Qwen3.5 fails with vLLM, still reasons with thinking off, or the new architecture behaves oddly | **Qwen3-8B** | L4 | The previous generation of the same family, more mature; Apache 2.0. Sources disagree on context (32K–128K, all enough for 3–5K-token prompts). Same family, so it does not avoid any Vietnamese weakness |
| Too slow or over budget | **Qwen3.5-4B** (the ADR's original fallback) | L4 or T4 | Cheapest; citation quality/prompt compliance usually drops, re-read samples |
| The Qwen family's Vietnamese is poor | **Gemma 4 E4B** (about 8B total, 4.5B effective) | A10 | Different family. Secondary sources state Apache 2.0 and 140+ languages; **Vietnamese is not listed explicitly**. Stated Hugging Face tag: `google/gemma-4-E4B-it` |
| A larger model that is still cheap | **Gemma 4 26B A4B** (MoE, 3.8B active of 25.2B total) | L40S | FP8 weights about 26 GB, so it does not fit L4/A10; much more expensive ($1.95/hour). Stated tag: `google/gemma-4-26B-A4B-it` |

**Judge constraint:** the table above makes Gemma 4 the faithfulness judge because it is a different family from the generator. If the generator moves to Gemma 4, the judge must move to another family (for example Qwen3.5-9B or Qwen3-8B) so it does not grade itself; update the judge row at the same time.

Considered but not proposed: Phi-4 14B (MIT according to most sources, but no Vietnamese evidence), Granite 3.1 8B (Apache 2.0, 128K, but from memory the official language list has no Vietnamese; not checked), Llama (licenses of recent versions conflict between sources), Mistral 7B v0.3 (old, 32K context).

**Model selection and testing criteria (the full bake-off; dropped by the owner on 2026-11-04, only the quick check above remains; the items below are the method if a serious comparison is wanted later):**
1. Run Qwen 3.5 9B and 4B on about 20 VI/EN questions from the eval set (including unanswerable ones), `temperature=0`, recording the model with revision.
2. Measure time to first token (TTFT) p50/p95 including cold starts, tokens/second, Modal cost per run and per question.
3. Measure prompt-rule compliance: `[n]` pointing to the right source, the fixed opening sentence when information is missing, answering in the question's language, never leaking the canary.
4. Choose the **smallest** model that meets all four: rule compliance not clearly worse than a larger model, acceptable TTFT for eval, total cost within budget. Otherwise use the fallback and record it.
5. Judge: compare with 30–50 hand-graded questions; record the agreement. The report states the limits of a small judge.
6. Every run writes a `run.json` with GPU type, duration and cost; set budget alerts (workspace budget) on both accounts, a short idle timeout (30–60 seconds), and stop the app after each session.

**Budget estimate (not measured, rough estimate on 2026-11-01):** bake-off about $3; development with the real model about $11; about 10 answer-evaluation runs about $7; about 10 judge runs on L40S about $11; the Vietnamese check set and latency measurement about $3; 50% contingency. Total about $50, within the $60 of two accounts for one month if runs are batched, containers are stopped when idle and development uses a stub or a local 4B model. Replace these figures with measured ones after the bake-off.

Not used: Gemini (any generation) and Groq `gpt-oss-120b` for the two tasks above, Groq `gpt-oss-safeguard-20b` (3 RPM). There is no LLM node for intent classification: greetings are answered by rules and a semantic router over the question embedding, without calling an LLM (owner decision 2026-10-20, V2-27; the LLM-classifier option for the grey zone was rejected), and questions below the evidence threshold are refused without calling the generator (PRD FR-12, FR-13). Data sent to Modal (self-hosted models) and Groq (metadata suggestions) leaves the owner's machine; the README must warn against loading real internal documents during demos.

**Design constraints imposed by B1:**
1. **At most 2 LLM calls per question:**
   - The guard calls no LLM (four rule layers, see §4.4); harmful content relies on rules and the generation model.
   - The main call: answer generation, with at most 5–6 chunks.
   - Question rewriting runs only when there is conversation history (the second and only other call). With self-hosted models this limit is a latency and cost target rather than a quota limit. Conversation titles are generated by a simple rule.
2. **Quotas** (FR-09): questions per user per day, plus one system-wide quota to protect provider quotas.
3. **A sleeping service runs no jobs.** core-api's outbox must *push* HTTP to ai-service to wake it, not rely only on a scheduler. ai-service's worker scans for pending jobs at every startup.
4. **No cron to keep services awake.** Render gives 750 hours/month shared across all services; keeping two services awake 24/7 would exhaust it. Before a demo, call once to wake them.
5. **Demo workspace:** a public workspace with a sample SOP set. New JIT users are added as `MEMBER` (read-only), behind a configuration flag. Visitors can ask right away without uploading. This is a small change to ADR-005 and needs owner approval.
6. **Google OAuth** must move the consent screen to *In production* so people outside the test list can sign in.
7. State clearly on the demo page: restart time, quotas, and that the data is demo data.

#### Option B2: one VM running docker compose (if a VM is available)
- Used when there is a VM with enough RAM, for example student credits (GitHub Student Developer Pack, Azure for Students). **The 2026 conditions of these programs have not been checked.**
- Runs the same compose as environment A, plus an HTTPS reverse proxy. Local bge-m3 and the reranker can be enabled.
- No code changes, only environment variables.

#### Option B3 (safe fallback): run on the local machine and expose it temporarily
- Run compose on the owner's machine and expose it with Cloudflare Tunnel (`cloudflared`, free) during interviews or live demos.
- Add a demo video and the eval report to the README for viewers who look when nobody has the machine on.
- Not a permanent deployment, but zero cost and the lowest risk.

**Suggested order:** A first, since it serves the research and runs on the same compose. Then B3 (almost no effort), then B1 once the features are stable.

## 5. Impact and consequences
- **Positive:**
  - Eval does not depend on quotas and is reproducible.
  - The deployment needs no VM and no model operations.
  - Providers are switched by configuration, so a removed model needs no code change.
- **Trade-offs:**
  - The deployment (B1) turns rerank off, so its quality is below the best eval configuration. The report must state this difference.
  - Vectors from Workers AI and from local bge-m3 may differ slightly. Eval metrics are measured on local bge-m3; the deployment uses its own index.
  - Cold start about 30–60 seconds (Render + Neon).
  - The LLM quota limits the system to a few hundred questions per day overall.
  - It depends on many free accounts, so a re-check checklist is needed (§6).
  - Data sent through the Gemini free tier may be used to improve products. The deployment contains only demo documents.
- **Next actions:**
  - Bring §4.1–§4.3 into TECH-V2-ai-service (provider interfaces, model configuration file, the 2-call LLM pipeline, the retrieval-score schema) and TECH-V2-core-api (push outbox for wake-up, demo workspace).
  - Create the `eval/` folder and the dataset format (FR-18).

## 6. Re-check list before deploying
- [ ] Groq: call `/models` with a real key; check the Deprecations page and the limits at `console.groq.com/settings/limits`.
- [ ] Gemini: check the current Flash-Lite model, the Deprecations page, the free limits in AI Studio and the data-use terms.
- [ ] Cloudflare: the neuron price of `bge-m3` and the Workers AI free limit; the R2 activation conditions.
- [ ] Render, Neon: RAM, run hours and sleep time of the free tiers.
- [ ] Google OAuth: publishing status and verification requirements for the `openid email profile` scopes.
- [ ] Check the cosine difference between Workers AI vectors and local bge-m3 vectors on about 100 sample chunks.

## 7. References (read 2026-10-16 → 2026-10-17)
- [Cloudflare Workers AI – Pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [Models](https://developers.cloudflare.com/workers-ai/models/)
- [Cloudflare R2](https://www.cloudflare.com/products/r2/), [R2 free tier – r2drop](https://r2drop.com/blog/cloudflare-r2-free-tier-guide)
- [Backblaze B2 review – cloudwards](https://www.cloudwards.net/backblaze-b2-review/)
- [Groq – Models](https://console.groq.com/docs/models), [Deprecations](https://console.groq.com/docs/deprecations), [Rate limits](https://console.groq.com/docs/rate-limits)
- [Gemini API – Deprecations](https://ai.google.dev/gemini-api/docs/deprecations), [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Free tier (10/2026) – klymentiev](https://klymentiev.com/blog/gemini-api-free-tier)
- [Hugging Face Spaces Overview](https://huggingface.co/docs/hub/en/spaces-overview)
- [Hosting free tiers (09/2026) – flaviocopes](https://flaviocopes.com/hosting-free-tiers/), [Hosting free tier comparison – agentdeals](https://agentdeals.dev/hosting-free-tier-comparison-2026)
- [Neon pricing](https://neon.com/pricing), [Neon free plan limits](https://neon.com/faqs/free-plan-limits-and-quotas)
- [VN-MTEB](https://arxiv.org/pdf/2507.21500), [Qwen3 Embeddings MTEB – Zilliz](https://zilliz.com/ai-faq/qwen3-embeddings-vs-alternatives-mteb-ranking)
- [TEI Intel CPU container](https://huggingface.co/docs/text-embeddings-inference/intel_container)
- [Oracle free tier changes 2026 – terminalbytes](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026)
- [MinIO archived – pinggy.io](https://pinggy.io/blog/minio_archived_self_hosted_s3_alternatives/)
