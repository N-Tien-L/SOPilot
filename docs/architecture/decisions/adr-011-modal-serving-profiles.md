---
id: ADR-011
title: "Answer model serving on Modal: one L40S deploy, 64K context, parallel eval and a warm demo"
status: approved
created: 2026-11-15
updated: 2026-11-16
author: "Owner"
deciders: ["Owner"]
amends: [ADR-006]
supersedes: []
superseded_by: []
refs:
  - infrastructure/modal/serve_vllm.py
  - infrastructure/modal/README.md
  - services/ai-service/config/models.yaml
  - eval/sopilot_eval/answers.py
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-34-infra-modal-llm-endpoint.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-35-infra-modal-rerank-shared-gpu.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-37-eval-config-matrix-answer-level.md
---

# ADR-011: Answer model serving on Modal: one L40S deploy, 64K context, parallel eval and a warm demo

Amends [ADR-006 §4.4](adr-006-free-tier-providers-and-environments.md) (answer-generation row: GPU and context). Approved by the owner on 2026-11-15; the profile was deployed and measured on 2026-11-16 under V2-40 (§5). Figures marked *estimate* come from arithmetic on the model config and GPU specifications (tool-assisted analysis, 2026-11-15), not from runs; §5 says which of them a measurement has replaced.

## 1. Context

The answer endpoint ([`serve_vllm.py`](../../../infrastructure/modal/serve_vllm.py), V2-34, V2-35) runs Qwen3.5-9B (FP8) with vLLM on one A10 (24 GB), with `bge-reranker-v2-m3` (fp32) in the same container, `--gpu-memory-utilization 0.85`, `--max-model-len 8192`, `@modal.concurrent(max_inputs=32)`, `scaledown_window=60`, `max_containers=1`. Cold start is about 160 s with the FlashInfer cache on its volume (about 320 s without).

Two uses with different priorities:

| Use | Volume | Priority |
|---|---|---|
| Research eval (V2-37 answer level) | `sop-main-v2`: 293 questions (239 test, 54 dev). `answers.py` answers each question twice (`expand` on/off), so about 480 generation calls per test run, plus judge calls on a fixed 30-question subset | Cost per run, wall-clock time, reproducible numerics, no OOM |
| Live examiner demo | Ad-hoc questions, 1–2 users | Questions that need many SOP pages answered well, short TTFT, smooth streaming, no cold start in front of examiners |

### 1.1 Memory is not what limits the context

The pinned config (`Qwen/Qwen3.5-9B`, revision `c202236…`, read 2026-11-15) is a **hybrid** model: of 32 layers, 24 are linear attention (Gated DeltaNet, fixed-size state) and 8 are full attention (`num_key_value_heads 4`, `head_dim 256`). Consequences (*estimate*):

- KV cache per token, bf16: 2 × 8 × 4 × 256 × 2 B = **32 KiB**. A 32K request needs about 1 GiB, a 64K request about 2 GiB.
- Linear-attention state per running request: about 48 MiB (24 × 32 × 128 × 128 × fp32), independent of length.
- A10 today: 0.85 × ~22.5 GiB ≈ 19.1 GiB for vLLM; FP8 weights ~10.5 GiB (embeddings and `lm_head` stay bf16); overhead ~1.5–2 GiB; KV pool **~6.5–7 GiB ≈ 200K tokens**. The 8K cap was a conservative default, not a memory limit. The startup log line `GPU KV cache size: N tokens` gives the real figure.
- The model's native context is 262K positions; no RoPE/YaRN scaling is needed up to 64K.

**Mismatch:** ADR-006 §4.4 calls Qwen3.5-9B "a dense 9B model". The checkpoint config says hybrid (linear + full attention). The parameter count is right; the KV arithmetic above depends on the hybrid layout.

### 1.2 What does limit it

- **Prefill compute.** TTFT grows linearly with prompt length. *Estimate* for a 64K prompt: ~20 s on A10, ~6–8 s on L40S (**measured 7.4 s, §5**), ~2–3 s on H100.
- **Decode bandwidth.** Single-stream speed follows memory bandwidth: A10 600 GB/s (~40–50 tok/s, extrapolated from the 24.3 tok/s measured on L4 in V2-34 §5), L40S 864 GB/s (~60–70 tok/s; **measured 52–61, §5**), H100 3.35 TB/s.
- **The ai-service context budget.** `retrieval.context.max_tokens` (3000), `context_k` (5), `section_max_tokens` (1200) and `SOPILOT_LLM_CONTEXT_MAX_TOKENS` in [`models.yaml`](../../../services/ai-service/config/models.yaml) cap the prompt before it reaches vLLM. Raising `--max-model-len` alone changes nothing.
- **The eval loop is sequential.** `answers_report` in [`answers.py`](../../../eval/sopilot_eval/answers.py) calls the model one question at a time, so vLLM's continuous batching is never used and the GPU is billed while it idles between tokens.

## 2. Decision

Serve the answer model from **one L40S deploy** used for both eval and the demo, with a **64K context**, the reranker in the same container, and the two uses differing only in client concurrency and in how long the container is kept warm.

### 2.1 Server (one configuration)

| Setting | Value | Reason |
|---|---|---|
| GPU | `L40S` (48 GB, Ada, native FP8) | Faster prefill and decode than A10 for long prompts; ~25 GiB KV pool (*estimate*, ~800K tokens; **measured 784,931 tokens, §5**), so 8 × 64K requests fit without preemption |
| `--max-model-len` | `65536` | Covers multi-page SOP questions; vLLM allocates KV by actual length, so short prompts cost nothing extra |
| `--gpu-memory-utilization` | `0.85` (unchanged) | The reranker keeps its ~2.5–3 GiB outside vLLM's share |
| `--kv-cache-dtype` | `auto` (bf16) | KV is already small; FP8 KV would add numerical noise to faithfulness metrics for little gain |
| `--max-num-seqs` | `8` | Matches eval concurrency; fewer CUDA graphs to capture, so a shorter cold start than vLLM's default |
| `--max-num-batched-tokens` | `16384` | Chunked prefill: a typical prompt prefills in one or a few chunks while other requests keep decoding |
| `@modal.concurrent(max_inputs=…)` | `8` | Same as `--max-num-seqs`; extra requests queue in Modal, not in vLLM |
| Reranker | Same container, fp32, `max_length=512`, unchanged (V2-35) | Scores stay comparable with RQ2; one container, one cold start. Add `torch.cuda.set_per_process_memory_fraction` in the reranker process so its PyTorch allocator cannot grow into vLLM's share (no-OOM guard) |
| Other flags | `--quantization fp8`, `--language-model-only`, chat template kwargs unchanged | |

### 2.2 Eval: parallel requests

- `answers.py` sends up to **8 requests concurrently** (a `--concurrency` option, default 1 to keep current behaviour). Results are written in question order so `per_question.jsonl` stays deterministic.
- Quality metrics (citation precision, refusal, faithfulness) come from the concurrent run. **Latency and TTFT are measured in a separate run at concurrency 1** on a fixed sample, because concurrent requests share the GPU and inflate latency.
- `scaledown_window` long enough (about 300 s) that dev and test runs back to back do not cold-start twice.
- **Every reported answer-level run uses this L40S deploy.** On A10 vLLM runs weight-only FP8 (Marlin W8A16); on L40S it runs W8A8. Outputs differ slightly, so results from the two GPUs are not mixed in the thesis. Earlier A10 answer runs (V2-10, `eval/results/answers-answers-hybrid-test`) are development evidence and are re-run on L40S if they are reported.
- *Estimate*: one test run (~480 calls, ~1.2K output tokens each with thinking on) takes ~25–40 min at concurrency 8, about **$1 per run**, against ~4–5 h and ~$5 sequential on A10.

### 2.3 Demo: sequential, long context, kept warm

- One question at a time from the UI; the same server configuration as §2.1.
- Before the session: raise `min_containers` to 1 and `scaledown_window` to about 900 s (Modal's autoscaler update or a redeploy; check the API for the installed Modal version), warm the container about 10 minutes ahead, and restore scale-to-zero afterwards. Cost ~$1.95 per warm hour (ADR-006 §4.4 price list).
- The answer streams its reasoning (`ReasoningBlock`, thinking on since 2026-11-15) so examiners see progress during long prefills.
- Prepare 3–5 demo questions that need several SOP pages and check them before the session (long-context answers from a 9B model can miss evidence in the middle of the prompt).
- Optional, not decided: MTP speculative decoding (`mtp_num_hidden_layers: 1` in the checkpoint) for faster single-stream decode in the demo. The vLLM 0.33 method name and acceptance rate are unchecked. If enabled for the demo only, the demo and eval configurations diverge; record it.

### 2.4 Same context budget for eval and the demo

The ai-service context budget (`retrieval.context.*`, `context_k`, `SOPILOT_LLM_CONTEXT_MAX_TOKENS`) used in the demo is also the one evaluated, at least on the `multi_passage` group in `answers.py`. Otherwise the thesis has no numbers for the behaviour shown to examiners. The new values are chosen when the change is implemented and recorded in `models.yaml` and TECH-V2-ai-service.

## 3. Alternatives considered

| Option | Why not |
|---|---|
| Keep A10, raise `--max-model-len` to 32K–64K | Fits in memory (§1.1) and is cheapest per hour, but a 64K prompt takes ~20 s to prefill (*estimate*), too slow for the demo; using A10 for eval and L40S for the demo would split the numerics |
| A10 for eval, L40S or H100 for the demo | Two deploys to maintain; eval numbers would not describe the demoed system (W8A16 vs W8A8) |
| H100 for everything | ~2× the L40S hourly price ($3.95/h, *to be checked* on Modal's pricing page); the eval budget gains little since a run is already about $1 on L40S |
| Reranker in a separate container | Two cold starts and two warm containers for the demo; no gain for a ~0.1–0.3 s GPU call per question |
| Reranker on the local CPU | 15.7–18.1 s per question (ADR-006 §4.4); too slow for both uses |
| FP8 KV cache | Halves an already small KV cache; adds numerical risk to faithfulness metrics; on Ampere it is not hardware-accelerated |
| Offline batch API instead of concurrent requests | vLLM's continuous batching already batches concurrent HTTP requests; no new code path or dependency |

## 4. Consequences

**Positive:** one server configuration for eval and the demo; 8× the current context; eval runs about 5× cheaper and faster (*estimate*); thesis numbers describe the demoed system.

**Negative:** L40S costs ~1.8× A10 per hour; the first cold start on L40S rebuilds the FlashInfer and torch.compile caches (~320 s), so warm it once after the switch; answer-level results from A10 are not comparable and are re-run if reported; the V2-37 judge app is also planned on an L40S, so both share the Modal budget.

**Follow-up (ticketed as [V2-40](../../execution/initiatives/v2-sopilot-mvp/tickets/V2-40-infra-modal-serving-profile.md), 2026-11-16):**
1. ~~`serve_vllm.py`: GPU `L40S`, the flags in §2.1, the reranker memory cap; update `infrastructure/modal/README.md`.~~ Done 2026-11-16 (deployed, §5).
2. ~~`answers.py`: `--concurrency` with deterministic output order; a separate latency run at concurrency 1.~~ `--concurrency` done 2026-11-16. The separate latency run is `bench_context.py ttft` on synthetic prompts at fixed sizes, not a run over an eval sample; `answers.py` records no latency.
3. ~~`models.yaml`: new context budget and `SOPILOT_LLM_CONTEXT_MAX_TOKENS`; update TECH-V2-ai-service.~~ Values set 2026-11-16 (§5). The `multi_passage` run with them is deferred to V2-37.
4. Measure and replace the estimates in this ADR: startup `GPU KV cache size`, VRAM, cold start, TTFT at 8K/32K/64K, tok/s, cost per eval run (`infrastructure/modal/bench_context.py`, `bench_thinking.py`, `test_endpoint.py`). Done 2026-11-16 (§5), except the cost of one eval run, deferred to V2-37.
5. ~~Fix the "dense 9B" wording in ADR-006 §4.4 (§1.1 mismatch).~~ Done 2026-11-15.

## 5. Measured results (V2-40, 2026-11-16)

One deploy of [`serve_vllm.py`](../../../infrastructure/modal/serve_vllm.py) with the §2.1 profile (vLLM 0.33.0, `Qwen/Qwen3.5-9B` FP8, reranker in the same container), Modal workspace `n-tien-l`, region as assigned (not pinned). The launch line in the Modal log carries `--max-model-len 65536 --kv-cache-dtype auto --max-num-seqs 8 --max-num-batched-tokens 16384 --gpu-memory-utilization 0.85`. Tools: [`bench_context.py`](../../../infrastructure/modal/bench_context.py) (`ttft`, `smoke`), the Modal app log (`modal app logs sopilot-vllm`).

| Item | §1–§2 estimate | Measured |
|---|---|---|
| `GPU KV cache size` at startup | ~800K tokens (~25 GiB) | **784,931 tokens**; vLLM reports 11.98× concurrency at 65,536 tokens per request |
| GPU memory, reranker loaded | reranker ~2.5–3 GiB outside vLLM | 41,130 of 46,068 MiB in use (`nvidia-smi`); reranker process 2.12 GiB allocated / 2.13 GiB reserved |
| TTFT, 8K prompt | not estimated | median **1.64 s** (8,024–8,029 prompt tokens, 3 runs) |
| TTFT, 32K prompt | not estimated | median **3.89 s** (32,238–32,243 tokens, 3 runs) |
| TTFT, 64K prompt | 6–8 s | median **7.36 s** (65,492–65,494 tokens, 3 runs; range 7.31–8.58 s) |
| Decode, single stream | 60–70 tok/s | median **61.5** tok/s at 8K, **56.9** at 32K, **51.9** at 64K (see the caveat below) |
| First request after deploy (client wall clock) | ~320 s without caches | **268 s**; vLLM was healthy 114 s after the container hook began, the rest is Modal scheduling and mounting. `torch.compile` took 18.8 s; the FlashInfer volume held 18 files before launch |
| Start with every cache warm (container idle for more than 300 s, then one request) | ~160 s (A10) | **92 s** client-side to `/health` `200`; vLLM healthy 73 s after the container hook began; `torch.compile` 1.9 s (18.8 s on the first start); `GPU KV cache size` 785,431 tokens; 39,873 MiB in use (41,130 MiB after the first start). Measured 2026-11-16 17:49 local time, 7 hours after the last request |
| Cost of one test run | ~$1 | **not measured**: deferred to V2-37 (see below) |

Each TTFT prompt starts with a random nonce, so the prefix cache cannot serve it. TTFT is client-side, from the request to the first content token, thinking off.

**Concurrency smoke (8 requests of about 32K tokens at once).** 8 of 8 completed in 25.4 s wall clock; per-request TTFT ranged 4.9–20.1 s because vLLM prefills them in chunks of 16,384 tokens while others decode. At 8 running requests the KV cache usage peaked at **33.5%**. In the log of the L40S run: 0 lines with `preempt`, 0 with OOM or `out of memory`, 0 tracebacks, and 45 of 45 chat completions answered `200 OK`. This meets the V2-40 smoke criterion; the dev-split eval at `--concurrency 8` was not run.

**Caveats.**
- The 64K prompts left 42–44 tokens of output (the context limit is 65,536 in total), so the 64K decode figure rests on very short outputs; read it as indicative. The 8K and 32K figures come from 154–223 output tokens.
- The 268 s figure is a first start after switching GPU type; the warm-cache start is the 92 s row. One sample each, so read both as indicative.
- The 1,000-token request used to time the first start, the calibration calls and the benchmark all hit the same container, so the log's 45 requests include them.
- Modal's price for L40S was not checked; no cost is quoted.
- TTFT is to the first **content** token with thinking off. The demo runs with thinking on, so the wait for the first answer token includes the reasoning; the 10 s limit of the V2-40 rule is met for prefill, not for a thinking answer. `bench_thinking.py` measures that.
- `@modal.concurrent(max_inputs=8)` is on the class, so the rerank web server probably shares the 8 slots with chat. With 8 long chat requests streaming, a rerank call may queue behind them (ai-service's rerank timeout is 30 s). How Modal counts inputs across the two `web_server` methods was not verified; check it before a parallel demo.
- A concurrent eval run needs client-side limits above the service defaults (`answers.py` raises them itself, see `eval/README.md`); the dev-split run at concurrency 8 has not been executed.

**Deferred by the owner (2026-11-16):** the `multi_passage` run with the chosen context budget, the dev-split eval at `--concurrency 8`, and the cost and duration of one eval run. The AI pipeline still has pending fixes, so a full eval now would spend Modal budget on an unfinalized pipeline. They move to [V2-37](../../execution/initiatives/v2-sopilot-mvp/tickets/V2-37-eval-config-matrix-answer-level.md), which already runs the answer-level evaluation on this deploy. Until then the context budget is a choice, not a result, and the 25–40 min and ~$1 figures of §2.2 stay estimates.

**What stays an estimate:** the A10 figures in §1, the H100 figures, and the cost and duration of an eval run (§2.2).

**Context budget chosen (§2.4), owner decision 2026-11-16.** Eval and the demo share one budget, declared in [`models.yaml`](../../../services/ai-service/config/models.yaml); the harness reads `context_k` from it instead of the eval config's `k`.

| Setting | Before | Now | Why |
|---|---|---|---|
| `retrieval.context_k` | 5 | **8** | more hit chunks for multi-page questions |
| `retrieval.context.section_max_tokens` | 1,200 | **3,000** | whole sections of several pages |
| `retrieval.context.max_tokens` | 3,000 | **16,000** | about 16K prompt tokens: TTFT interpolates to roughly 2.5–3 s between the measured 1.64 s (8K) and 3.89 s (32K); not measured at 16K |
| `SOPILOT_LLM_CONTEXT_MAX_TOKENS` | empty | **60,000** | 65,536 served − 3,000 output tokens − margin |

The V2-40 rule holds with room: 8 × (60,000 + 3,000) = 504,000 ≤ 784,931 KV tokens, and the measured TTFT at 65K is 7.36 s (limit 10 s). The working budget (16K) is far below the ceiling on purpose: a 9B model can miss evidence in the middle of a long prompt, and a larger source budget raises TTFT and eval cost. **Not yet evaluated:** the `multi_passage` group of `answers.py` with these values (deferred to V2-37, see above); until then the budget is a choice, not a result.
