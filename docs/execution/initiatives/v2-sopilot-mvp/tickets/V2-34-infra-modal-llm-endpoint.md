---
id: V2-34
title: "Infra: self-hosted LLM endpoint (Qwen3.5-9B FP8, vLLM) on Modal and a quick check"
type: chore
status: done
created: 2026-11-09
updated: 2026-11-13
author: "Owner"
scope: infra
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-02]
blocks: [V2-10, V2-35]
branch: "infra/modal-llm-endpoint"
assignee: pair
---

# TICKET V2-34: Self-hosted LLM endpoint on Modal

> **Scope:** `infra` | **Size:** `M` | **Priority:** `P0`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `infra/modal-llm-endpoint`

> Translated from Vietnamese on 2026-11-13; content unchanged.

---

## 1. Context & goal
The owner settled the answer model as Qwen3.5-9B FP8, vLLM, an L4 GPU (A10 if L4 is too slow) and a quick check of about 20 questions before committing (ADR-006 §4.4, "Settling the answer model"). `V2-10` needs a real endpoint to run that quick check and manual tests. This ticket builds and checks an OpenAI-compatible endpoint on Modal; it **does not change `services/ai-service` code**. The model decision, costs and alternative candidates are in ADR-006 §4.4 and not repeated here.

Limits:
- The infrastructure lives outside the repo. No dependency added to `pyproject.toml`. The Modal scripts live in `infrastructure/modal/` (owner approved 2026-11-09).
- Real keys and URLs are not written into the repo or docs; use placeholders (`<LLM_BASE_URL>`, `<LLM_API_KEY>`).
- **Data warning:** every prompt sent to Modal leaves the owner's machine. Test runs use only `sop-main`/sample data, never real internal documents.

---

## 2. Acceptance criteria
Each criterion has a check; results go into section 5 (evidence) when done.

- [x] A Modal endpoint runs vLLM with Qwen3.5-9B FP8 on L4 (A10 if L4 is too slow), serving `/v1/chat/completions` and `/v1/models`. *Check:* `test_endpoint.py` with the owner's key: `/v1/models` returns 200 with the right model id, all 17 streamed chat turns return results (section 5).
- [ ] Record the model id, revision, GPU, date and cost per startup (ADR-006 §4.4). *Check:* the table in section 5 has every column, revision taken from Hugging Face. *Missing:* the real cost from Modal's Usage page (currently only an estimate from the measured time). → *Owner settled 2026-11-09: close the ticket, the missing part becomes a `V2-10` criterion.*
- [x] `enable_thinking=false` takes effect through `chat_template_kwargs` (and/or `--default-chat-template-kwargs`). *Check:* send the same question with and without the flag and compare the output tokens (`usage.completion_tokens`) with the visible answer length; compare with the Jinja template of the pinned revision (section 5).
- [x] Measure cold and warm TTFT and tokens/second on a sample turn (`temperature=0`, stream). *Check:* `test_endpoint.py --benchmark` on 2026-11-09; numbers, GPU and method in section 5.
- [x] The key lives only in the owner's environment, not in the repo; `.env.example` has `SOPILOT_LLM_*` variables with dummy values (present since `V2-10` milestone 2). *Check:* `./scripts/check-env.ps1` and gitleaks report nothing; `git diff` has no real key or URL.
- [ ] Check Modal's terms on using two Starter accounts (ADR-006 §4.4 says "not checked") and record the conclusion with the date read. *Check:* read the terms of service and pricing page; the conclusion goes into section 5 with the quoted clause and link; if not allowed, tell the owner to amend ADR-006 §4.4. *Missing:* a verbatim quote of the clause. → *Owner settled 2026-11-09: close the ticket, the missing part becomes a `V2-10` criterion.*
- [ ] The expected cost stays within the $30/month allowance per account; record the limits: scale-to-zero, a short idle timeout (30–60 seconds), no pinned region, no non-preemptible, a workspace budget alert. *Check:* the applied configuration is listed in section 5; the real cost of the quick check compared with the ADR's $1–3 estimate. *Missing:* the real cost and confirmation that the budget alert is set. → *Owner settled 2026-11-09: close the ticket, the missing part becomes a `V2-10` criterion.*

---

## 3. Implementation guide
1. **Script review (owner).** The owner approved the `infrastructure/modal/` location on 2026-11-09. Created `serve_vllm.py`, `test_endpoint.py`, `README.md`.
2. **Deploy.** vLLM serves an OpenAI-compatible API, weights cached in Modal Volumes (`sopilot-hf-cache`, `sopilot-vllm-cache`), scale-to-zero (`scaledown_window=60`), protected by a Bearer token in the Modal Secret `sopilot-vllm-secret`.
3. **Check** per section 2 with `python infrastructure/modal/test_endpoint.py`.
4. **Record results** in section 5.
5. **Hand over to `V2-10`:** the owner sets `SOPILOT_LLM_*` in their own `.env` (not written into the repo).

---

## 4. Testing
| Kind | Content | Tool | Command |
|---|---|---|---|
| Manual | `/v1/models`, `/v1/chat/completions`, the `enable_thinking` flag, cold/warm TTFT, tokens/second | `test_endpoint.py` / `curl` | `python infrastructure/modal/test_endpoint.py --benchmark` |
| Syntax & docs | Python compile, frontmatter, `depends_on`/`blocks` relations, links | `python -m py_compile`, `check-docs.ps1` | `./scripts/docs/check-docs.ps1` |

---

## 5. Evidence

| Item | Value |
|---|---|
| Model id / revision | `Qwen/Qwen3.5-9B` (revision SHA: `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, Apache 2.0) |
| GPU | NVIDIA L4 (24 GB VRAM) |
| Run date / configuration | 2026-11-09. vLLM `0.33.0`, image `nvidia/cuda:13.0.2-devel-ubuntu22.04`, `--quantization fp8`, `--language-model-only`, `--max-model-len 8192`, `--gpu-memory-utilization 0.90`, `--default-chat-template-kwargs '{"enable_thinking": false}'`. Cost limits: `scaledown_window=60`, no pinned region, no non-preemptible, Bearer key in a Modal Secret (deploy refused if the key is missing). |
| Cost per startup | **Estimate, not reconciled with Usage:** cold start 494 seconds × $0.000222/second L4 GPU ≈ $0.11 (excluding CPU/RAM). The whole measurement run (startup + 17 generations of ~11K tokens + 60 seconds waiting to scale to 0) is about 17 GPU minutes ≈ $0.23, plus CPU/RAM estimated at ~$0.06 → ~$0.30. Real cost: — |
| Cold / warm TTFT, tokens/second | Measured from the owner's machine (Vietnam) to the `us-east` endpoint, stream, `temperature=0`, 15 sample VI/EN questions (5 negative), no RAG context. **Cold:** 494 seconds from calling `/v1/models` with the container at 0 until the server is ready (boot, loading weights from the Volume, FP8 quantization, compilation), close to the 600-second `startup_timeout`. **Warm:** mean TTFT 1145 ms (975–1289 ms), measured client-side so including network latency and the TLS handshake of each request. **Generation speed:** 24.3 tokens/second (24.2–24.5), token counts from `usage`. Answers are 129–1422 tokens long, about 5–58 seconds each. |
| `enable_thinking=false` result | The same Vietnamese question: `false` → 214 tokens, 772 characters, no `<think>`/`</think>` tags; `true` → 1449 tokens, 4926 characters, with a "Thinking Process" block and a `</think>` tag. Output tokens match the visible answer length, so the flag **stops generating** reasoning rather than just hiding tokens. Matches the `chat_template.jinja` of the pinned revision: when `enable_thinking is false` the template inserts `<think>\n\n</think>\n\n`; without the flag reasoning is on by default, hence `--default-chat-template-kwargs`. |
| Two-account terms conclusion | **No verbatim quote yet; the owner needs to recheck.** Initial note (2026-11-09, `modal.com/terms`): creating multiple personal accounts to get around limits or accumulate free credit (credit farming/circumvention) is **strictly prohibited**. Violations may lead to suspension of all related accounts. **Conclusion:** operate on **a single Starter account** ($30/month free compute), with a tightly managed idle timeout (60s). ADR-006 §4.4 needs amending to record this conclusion. |

---

**Acceptance (owner, 2026-11-09):** `done`. The endpoint, the `enable_thinking` flag and the TTFT/tokens-per-second measurements have real evidence (DoD 1, 3, 4, 5). DoD 2, 6, 7 lack sufficient evidence; the owner accepted closing and moving them to `V2-10`: real cost versus the estimate, the budget alert, quoting Modal's terms on multiple accounts and amending ADR-006 §4.4 (the budget is currently computed on two accounts). Known risk: the 494-second cold start is close to the 600-second `startup_timeout`; warm up the endpoint before running evals or demos.

---

## 6. Changed files
- `infrastructure/modal/serve_vllm.py` (new): vLLM deployment on a Modal L4, volume caching, scale-to-zero.
- `infrastructure/modal/test_endpoint.py` (new): endpoint check script, thinking flag, TTFT/throughput benchmark.
- `infrastructure/modal/README.md` (new): how to set up the secret, deploy, test and configure `.env`.
- `docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-34-infra-modal-llm-endpoint.md`: status and evidence updated.
- `docs/execution/initiatives/v2-sopilot-mvp/PLAN.md`: `V2-34` moved to `in-progress`.
