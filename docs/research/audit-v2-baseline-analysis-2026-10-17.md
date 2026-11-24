---
id: AUDIT-V2-BASELINE-ANALYSIS
title: "Baseline analysis for V2: features, auth, AI models, retrieval and trade-offs"
type: audit
status: final
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [all]
verdict: FAILED
---

> Translated from Vietnamese on 2026-11-13; content unchanged. Provider and deployment assumptions are as of the dates given; ADR-006 §4.4 records the later decisions (local only, self-hosted Modal models since 2026-11-01, departments restored by ADR-007).

# BASELINE ANALYSIS FOR V2

> **Report id:** `AUDIT-V2-BASELINE-ANALYSIS` | **Dates:** `2026-10-16 → 2026-10-17` | **Conclusion:** `FAILED`. The current code does not meet the V2 goals (multi-tenant, 0 USD/month) without a redesign.
>
> This report records the analysis that led to [PRD-V2](../product/prd-v2-sopilot-mvp.md), [ADR-004](../architecture/decisions/adr-004-two-service-architecture.md), [ADR-005](../architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md) and [ADR-006](../architecture/decisions/adr-006-free-tier-providers-and-environments.md). It is an analysis by reading code and docs; **no tests were run** in this round.

---

## 1. Summary

- **The owner's new goal:** SOPilot serves many organizations (from individuals and startups to enterprises), with Google JIT sign-in. The project targets a CV (AIE in Python + SWE in Java) and a university research report, not commercialization yet. Target cost 0 USD/month. Rebuild right in this repo.
- **Main conclusions:**
  1. The system has no tenant concept, so there is a risk of cross-organization data leaks (section 3).
  2. The 8-service + RabbitMQ + Redis architecture cannot be hosted for free (section 2).
  3. Most configured LLM models **have been shut down by their providers** (section 4).
  4. The reranker was never wired into the pipeline, and retrieval scores mix scales (section 5).
  5. The free tiers of Jina, MinIO community, Hugging Face Spaces and Oracle all have problems. Alternatives are recorded in ADR-006.

---

## 2. Feature analysis (keep or cut)

Scope details are in PRD-V2 §5. The main reason for each group:

| Group | Decision | Reason |
|---|---|---|
| Q&A with citations, evidence-based refusal | Keep, as the core | This is the core value and the subject of the research (RQ1–RQ3) |
| Workspaces, membership, invitations, joining by domain | Add | Required to serve many organizations and individual users |
| HR roster, departments, department-based access rules | Cut | Blocks individual users; an enterprise can use several workspaces instead |
| Passwords, OTP, session management | Cut | Google sign-in only; smaller attack surface |
| OnlyOffice, version comparison, analytics, export, metadata suggestions | Cut | Not core; costly to maintain and to host |
| Multi-layer intent classification, choosing the LLM in the UI | Cut | Costs 5–6 LLM calls per question and drains the free quota (section 4.3) |
| Eval harness, tenant isolation test suite | Add | Numbers are needed for the research submission and to prove zero leaks |

---

## 3. Auth and tenancy (code as of 2026-10-16)

**Good parts, worth porting to V2:**
- `GoogleTokenVerifierService` checks RS256 through JWKS, `iss`, `aud`, `exp`, `email_verified`.
- Identity is linked by `(issuer, sub)` in `core.external_identities` (`012_google_identities.sql`), not matched by email.
- `insertIfAbsent` against races, roster locking with `FOR UPDATE`, detection of reused refresh tokens.

**Problems:**

| # | Problem | Location | Severity |
|---|---|---|---|
| A1 | No tenant/organization in the schema, JWT or spec | The whole system | Critical |
| A2 | RAG retrieval filters only by role/department/user, not by organization, so documents may leak across organizations | `ai-qa-service/src/db/repositories/chunk_repo.py` | Critical |
| A3 | `department_id` is concatenated into SQL with an f-string | `chunk_repo.py:49` | High |
| A4 | Roster emails are globally unique | `010_employee_roster.sql` | High (for multi-tenancy) |
| A5 | A name must be in the roster to sign in, so individual users are blocked | `AuthService.java:196-260`, `EmployeeRosterService.admitGoogleLogin` | High |
| A6 | Two parallel auth flows (Google and password/OTP); a fake password hash `GOOGLE_OAUTH_JIT_UNUSABLE_PASSWORD` | auth-service | Medium |
| A7 | Both auth-service and user-service write `core.users` | auth-service, user-service | Medium |
| A8 | `e.getMessage()` is returned straight to the client | auth-service | Medium |
| A9 | The Google ID token `nonce` is not checked | `GoogleTokenVerifierService` | Medium |

Resolution: ADR-005 (the workspace is the tenant, application filtering + RLS, workspace-bound tokens).

---

## 4. AI models used in the code

### 4.1 Inventory (checked against the official deprecation pages on 2026-10-17)

| Where used | Model | Status | Proposed replacement |
|---|---|---|---|
| Toxicity filter, intent classification, short answers, question rewriting, title generation (`ai-qa-service/src/config/settings.py`, `services/pipeline/*.py`) | Groq `llama-3.1-8b-instant` | ❌ Groq lists it as shut down for free/developer plans from 2026-08-16 | `openai/gpt-oss-20b` |
| Fallback LLM (`services/generation/model_registry.py`, `llm_client.py`); metadata suggestions (`ingestion-service/.../metadata_suggestion_service.py`); `GROQ_MODEL` in compose | Groq `llama-3.3-70b-versatile` | ❌ Shut down from 2026-08-16 | `openai/gpt-oss-120b` |
| Fallback LLM `groq/qwen3-32b` | `qwen/qwen3-32b` | ❌ Shut down from 2026-07-17 | `openai/gpt-oss-120b` |
| Default value for the toxicity filter (`layer1_toxic_filter.py:125`) | `meta-llama/llama-guard-3-8b` | ❌ Shut down from 2025-06. Its replacement `llama-guard-4-12b` was also shut down from 2026-03 | `openai/gpt-oss-safeguard-20b` (preview) |
| Jailbreak blocking (`layer1_model`) | `meta-llama/llama-prompt-guard-2-86m` | ⚠️ Still running but as a preview | Keep, with a fallback |
| `gemini/flash-2` | `gemini-2.0-flash` | ❌ Google lists the earliest shutdown date as 2026-06-01 | The Gemini Flash / Flash-Lite 3.x line |
| `openrouter/mistral-7b` | `mistralai/mistral-7b-instruct` | ⚠️ Still on OpenRouter but paid | Drop |
| `local/qwen3-8b` (default) | self-hosted `qwen3-8b` | ✅ Works but needs a GPU or a lot of RAM | Only for local eval runs |
| Embedding (both services, compose) | `jina-embeddings-v3` | Still running, but the free tier is a one-time quota and non-commercial only | `bge-m3` (ADR-006) |

Groq's model list page still lists `llama-3.1-8b-instant` and `llama-3.3-70b-versatile`. The deprecation page says they are shut down for free/developer plans, available only to enterprise customers. Called with a real key on 2026-10-20 (V2-02, `eval/provider_check/check_providers.py`): Groq `/models` HTTP 200 (11 models), Gemini `/models` HTTP 200 (63 models). The script only checks the models V2 will use (the quota table below); the status of the old Llama/Qwen models in the table above was not confirmed directly, so the "Status" column still relies on the deprecation page.

#### Free-tier limits (captured by the owner on 2026-10-19)

| Provider | Model | RPM | RPD | TPM | TPD | Test calls (V2-02) |
|---|---|---:|---:|---:|---:|---|
| Gemini | Gemini 3.1 Flash Lite | 15 | 500 | 250K | — | 2026-10-20 (first): both IDs returned HTTP 503 (overloaded). 2026-10-20 (second, 10:19): `gemini-3.1-flash-lite-preview` HTTP 200 (7.4 s); `gemini-3.1-flash-lite` still HTTP 503. The model ID must be configurable, defaulting to `-preview`. 2026-11-01: `/models` HTTP 200 (60 models); `-preview` HTTP 200 (3134 ms); without `-preview` HTTP 200 (7280 ms). No longer used for answer generation (owner decision 2026-11-01, self-hosted on Modal) |
| Gemini | Gemini 2.5 Flash / 3 Flash / 3.6 Flash | 5 | 20 | 250K | — | |
| Gemini | Gemini 2.5 Flash Lite | 10 | 20 | 250K | — | |
| Gemini | Gemini 2 Flash, 2 Flash Lite, 2.5 Pro, 3.1 Pro | 0 | 0 | 0 | — | Not usable on the free tier |
| Groq | `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` | 30 | 1K | 8K | 200K | 2026-10-20: `gpt-oss-120b` HTTP 200 (492 ms; second: 663 ms), `gpt-oss-20b` HTTP 200 (569 ms; second: 461 ms). 2026-11-01: `/models` HTTP 200 (11 models); `gpt-oss-120b` HTTP 200 (697 ms); `gpt-oss-20b` HTTP 200 (508 ms). `gpt-oss-120b` is no longer the generation fallback or the judge; `gpt-oss-20b` is still used for metadata suggestions |
| Groq | `meta-llama/llama-prompt-guard-2-86m`, `-22m` | 30 | 14.4K | 15K | 500K | 2026-10-20: 86m HTTP 200, output is a probability as text, p50 316 ms; failed the test (below) |
| Groq | `openai/gpt-oss-safeguard-20b` | 3 | 1K | 2K | 200K | |

Role assignment chosen from this table: ADR-006 §4.4.

#### Prompt Guard 2 86M test (V2-02, 2026-10-20)

A 100-question set `eval/provider_check/prompt_guard_cases.jsonl` (drafted by the agent, not reviewed question by question by the owner), script `eval/provider_check/check_providers.py`; the raw result `eval/provider_check/results/summary-20261020-001108.md` is kept locally only (the `results/` folder is in `eval/.gitignore`); the main numbers are copied into the table below.

| Configuration | VI attacks blocked | EN attacks blocked | Easily-confused questions wrongly blocked (VI / EN) | Chunks wrongly blocked (VI / EN) |
|---|---|---|---|---|
| Prompt Guard, threshold 0.5 | 4/20 | 13/20 | 0/10 / 2/10 | 0/10 / 1/10 |
| Rules (regex) | 16/20 | 16/20 | 1/10 / 0/10 | 1/10 / 1/10 |
| Prompt Guard OR rules | 17/20 | 20/20 | 1/10 / 2/10 | 1/10 / 2/10 |

- Vietnamese is almost never recognized, even direct instruction-override questions; consistent with the model card (Vietnamese is not among the evaluated languages).
- It wrongly blocks valid English questions ("Ignore the previous version of the SOP…" 0.97, "Forget my last question…" 0.999) and an SOP chunk ("Ignore any instructions received by email…" 0.99), so it cannot be used to scan document chunks either.
- Conclusion: fails the criteria (false blocks ≤ 2%, VI attacks blocked ≥ 70%). The guard uses rules (owner's final decision 2026-11-01; the owner reviewed the whole 100-question set). The rerun on 2026-11-01 skipped Prompt Guard (`--skip-guard`) and only reproduced the rules baseline: attacks blocked 16/20 in both VI and EN, ordinary questions wrongly blocked 0/10, easily-confused questions VI 1/10 and EN 0/10, chunks VI 1/10 and EN 1/10. The rules' numbers are optimistic because the rules were written on this very set; a separate check set is needed when settling the rules in V2-10.

### 4.2 Embedding-related bugs
- `ingestion-service/src/services/embedding_service.py:27` hard-codes `EMBEDDING_MODEL_NAME = "BGE_M3"`, while the actual default model is Jina. So the cache and chunks record the wrong model name. This is exactly ticket NEXT-05's problem. V2 uses a new database, so the bug does not carry over, but **this code must not be ported as is**.
- Text is truncated to 512 tokens with `tiktoken` (OpenAI's tokenizer), not the embedding model's tokenizer. bge-m3 can read up to 8192 tokens.
- The enum `frontend/web/interfaces/enums/knowledge/embedding-model.enum.ts` lists OpenAI models the system does not use.

### 4.3 LLM quota pressure
- Each question can currently call the LLM 5–6 times: guard, toxicity filter, intent classification, question rewriting, title generation, answer generation. The answer generation call alone carries about 10 chunks, about 4 thousand prompt tokens.
- Groq's limits page lists `gpt-oss-20b` and `gpt-oss-120b` at 30 requests/minute, 1 thousand requests/day, 8 thousand tokens/minute and 200 thousand tokens/day. The page says this is the Developer plan; the free plan may be lower. At that level the system can answer only **about 30–40 questions/day**.
- Embedding is the opposite, with plenty of headroom: a 100-page document costs about 60 thousand tokens, a question about 30–50 tokens.
- **Conclusion:** V2 must cut the LLM calls to 2 per question (guard + answer generation) and set per-user limits. Details in ADR-006 §4.3.

---

## 5. Retrieval and the reranker

The current flow: embed the question → vector search (top 50) + BM25 (top 50) → merge with RRF (k=60, weights 0.7/0.3) → filter by `similarity_threshold=0.15` → take 25 chunks → [rerank, keep 10] → knowledge-gap detection → the prompt uses at most 10 chunks.

| # | Finding | Location | Consequence |
|---|---|---|---|
| R1 | **The reranker never runs.** `PipelineOrchestrator()` is created without passing `reranker_service`, so the field is `None` | `api/routes/chat.py:42`, `pipeline_orchestrator.py:80, 235, 439` | `USE_RERANKER` has no effect. No test touches the reranker |
| R2 | RRF uses its scores only for ordering and does not write them into `similarity_score`. Each chunk keeps its original score: cosine if it came from vectors, normalized `ts_rank` if from BM25 | `hybrid_search.py:97, 109-136` | The 0.15 threshold compares two mixed scales |
| R3 | Threshold filtering runs before the rerank step | `hybrid_search.py:97` | Wrongly removed chunks cannot be rescued by the reranker |
| R4 | The reranker overwrites `similarity_score` with its own score, while gap detection still uses the 0.15 threshold | `reranker.py:51`, `knowledge_gap.py:48` | Turning rerank on or off changes the number of questions marked "cannot answer", even though the documents are unchanged |
| R5 | The score returned to the frontend comes straight from `similarity_score` | `api/routes/chat.py:50` | The displayed score scale changes with the configuration |

**What the reranker means for V2:**
- The reranker reorders existing candidates; it does not find new chunks.
- Expected to raise Recall@5, nDCG and MRR, at the cost of extra latency (roughly 1 to a few seconds on CPU for 25 pairs, not measured).
- When the top results are more reliable, the number of chunks in the prompt can drop from 10 to 5. The number of questions answerable per day within the same LLM quota therefore nearly doubles.
- V2 stores `dense_score`, `bm25_score`, `fusion_score` and `rerank_score` separately. Rerank runs before threshold filtering. Each mode has its own threshold, calibrated on the eval set. This is the subject of RQ2 and RQ3.

---

## 6. Infrastructure and free providers (summary, details in ADR-006)

| Item | Finding |
|---|---|
| MinIO community | Stopped publishing Docker images from 2025-10, the repo was archived around 2026-02. Only pinned versions run, with no more security patches |
| Jina | The free tier is a one-time quota (most sources say 10 million tokens, some 1 million), non-commercial only, limited to 100 requests/minute |
| Oracle Always Free | Many sources say it was cut from 4 OCPU / 24 GB to 2 OCPU / 12 GB around 2026-06, and often reports no capacity. The owner decided not to use it because of the risk of wasted time |
| Hugging Face Spaces | Official docs: Docker or Gradio Spaces **require a paid plan to create**. Spaces only connect out on ports 80, 443 and 8080, so they cannot reach Postgres on port 5432 |
| Cloudflare Workers AI | Free 10 thousand neurons/day, refilled daily. `bge-m3` costs 1,075 neurons per million tokens, which works out to about 9 million tokens/day. Has `bge-m3` and `qwen3-embedding-0.6b`. The only reranker is `bge-reranker-base`, weak in Vietnamese |
| Free PaaS | Render: 512 MB RAM, sleeps after 15 minutes. Koyeb: inconsistent sources. Fly.io: trial only. Railway: very little credit. Cloud Run: free by GB-second, needs a card |
| Postgres | Neon Free: 0.5 GB and 100 CU-hours per project, has pgvector, auto-suspends after 5 minutes idle |

---

## 7. Trade-offs accepted (once the PRD/ADRs are approved)

| # | Trade-off | Mitigation |
|---|---|---|
| T1 | Losing departments and department-based permissions | Use several workspaces; add "groups" after V2 |
| T2 | Permission revocation lags by up to the access token lifetime (≤ 15 minutes) | Recheck membership on refresh; add a `jti` deny list if needed |
| T3 | A new database with Flyway, dropping the old local data | No production data; reset volumes only when the owner asks |
| T4 | Outbox + polling instead of RabbitMQ, ingest delayed by a few seconds | Enough for MVP load; the contract stays the same if a broker is adopted later |
| T5 | Dropping the gateway loses role-based rate limits and circuit breakers | Limits set inside the services; a reverse proxy for a single origin |
| T6 | Google sign-in only | Dev login in the local/test profile; publish the OAuth consent screen before demos |
| T7 | Complex RLS (`SET LOCAL` per transaction; the DB role is not the table owner) | The FR-19 test suite must run in CI |
| T8 | Workspace-bound tokens, so tabs open on different workspaces compete for the token | The frontend keeps tokens per workspace, or one active workspace per browser |
| T9 | Dependence on free tiers: cold starts, quotas, terms may change | Wake up with a call before demos, per-user limits, embedding cache, local eval runs, provider configuration through env |
| T10 | Most of the Java code must be rewritten | Selective porting (section 3); the old code runs alongside until V2 reaches parity |
| T11 | Data sent to the Gemini free tier may be used by Google to improve its products | Deploy only with public demo documents; state it clearly in the report |

---

## 8. Next steps
- [ ] Owner reviews PRD-V2, ADR-004, ADR-005, ADR-006.
- [ ] Write TECH-V2-core-api and TECH-V2-ai-service (bringing findings R1–R5 and §4.2 into the design).
- [x] Call Groq `/models` with a real key to confirm section 4.1 (2026-10-20, V2-02).
- [ ] Draw up PLAN-V2 and the tickets.

## 9. References (read 2026-10-16 → 2026-10-17)
- [Groq – Deprecations](https://console.groq.com/docs/deprecations), [Groq – Models](https://console.groq.com/docs/models), [Groq – Rate limits](https://console.groq.com/docs/rate-limits)
- [Gemini API – Deprecations](https://ai.google.dev/gemini-api/docs/deprecations), [Gemini API – Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Cloudflare Workers AI – Models](https://developers.cloudflare.com/workers-ai/models/), [Pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Hugging Face Spaces Overview](https://huggingface.co/docs/hub/en/spaces-overview)
- [MinIO maintenance mode – elest.io](https://blog.elest.io/minio-is-in-maintenance-mode-your-guide-to-s3-compatible-storage-alternatives/), [MinIO archived – pinggy.io](https://pinggy.io/blog/minio_archived_self_hosted_s3_alternatives/)
- [Jina Embeddings](https://jina.ai/embeddings/), [Jina pricing – markaicode](https://markaicode.com/pricing/jina-ai-pricing/)
- [Oracle free tier changes 2026 – terminalbytes](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026)
- [Hosting free tiers (09/2026) – flaviocopes](https://flaviocopes.com/hosting-free-tiers/)
- [Neon pricing](https://neon.com/pricing)
- [OpenRouter – mistral-7b-instruct providers](https://openrouter.ai/mistralai/mistral-7b-instruct/providers)
