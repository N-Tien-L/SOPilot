---
id: V2-35
title: "Infra + ai-service: bge-reranker-v2-m3 rerank on GPU, sharing the A10 container with vLLM"
type: feat
status: done
created: 2026-11-09
updated: 2026-11-13
author: "Owner"
scope: infra
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-34]
blocks: [V2-18, V2-37]
branch: "feat/infra-modal-rerank"
assignee: pair
---

# TICKET V2-35: Rerank on the GPU shared with the vLLM container

> **Scope:** `infra` + `ai` | **Size:** `L` | **Priority:** `P1`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `feat/infra-modal-rerank`

> Translated from Vietnamese on 2026-11-13; content unchanged.

---

## 1. Context & goal
Reranking with `bge-reranker-v2-m3` on CPU takes 15.7–18.1 seconds per question ([AUDIT-eval-rq1-rq3](../../../../research/audit-eval-rq1-rq3-2026-11-04.md) RQ2/RQ2b), so `V2-07` does not enable it by default. The default retrieval mode (hybrid, dense or with rerank) is still open and was moved to `V2-10`/`V2-18` ([V2-07](V2-07-run-rq1-rq3-rq5.md) §6).

This ticket moves the reranker onto the A10 GPU **in the same Modal container** as `V2-34`'s vLLM (`infrastructure/modal/serve_vllm.py`), to get real latency numbers and rerun RQ2/RQ2b quickly. The owner chose the shared-container option on 2026-11-09. Reason: no extra GPU and no separate cold start. A separate rerank endpoint on the owner's second Modal account remains the fallback if the shared container does not work out (VRAM, TTFT).

Limits:
- Keep the RQ2/RQ3 score scale: use sentence-transformers `CrossEncoder`, `max_length=512`, take the raw logits and apply the sigmoid client-side as `LocalRerankProvider` does. Do not use vLLM's `/score` pooling endpoint.
- The `bge-m3` embedder still runs locally.
- Do not enable rerank by default, do not choose the default retrieval mode, do not tune `thresholds.hybrid_rerank`. Those are decided after this ticket's measurements.
- **Data:** chunk content is sent to Modal, at the same level as the current prompts. Use only `sop-main`/`sop-main-v2` and sample data.

---

## 2. Acceptance criteria

**Decisions before starting (owner)**

- [x] Behaviour when rerank fails or times out: (a) stop as now (`RerankError` → the turn fails), or (b) fall back to `hybrid` without rerank (changing the gate and thresholds midway). Proposed (a).
  *Settled:* (a), as proposed, after the owner had the trade-off explained and asked for the remaining open items to be finished (2026-11-09). The code stops with `RerankError` and does not fall back to hybrid. The owner reconfirms at acceptance.
- [x] Agree to add `sentence-transformers` to the Modal image. If the gateway option is chosen in Step 0, add `fastapi` too (CLAUDE.md, rule 12). No change to ai-service's `pyproject.toml`.

**Modal infrastructure**

- [x] A spike (Step 0) decides the option: two `@modal.web_server` in one `@app.cls` sharing a container (no proxy needed), or a FastAPI gateway on the exposed port forwarding `/v1/*` (including SSE) to vLLM on `127.0.0.1`. Record the result in section 5.
- [x] The container loads the reranker first, then starts vLLM with `--gpu-memory-utilization` lowered from 0.90 (proposed 0.85); `--max-model-len 8192` still starts. Record the measured VRAM.
  Measured VRAM: 21,180 / 23,028 MiB used when vLLM is ready; the reranker holds 2.12 GiB (section 5).
- [x] `POST /v1/rerank` takes `{query, passages[]}` and returns `{logits[]}` in the same order as `passages`. Checks the Bearer with `hmac.compare_digest` against `VLLM_API_KEY`: a missing or wrong key returns `401`; neither the key nor passage content is logged.
- [x] `/v1/models` and streamed chat still work as in `V2-34`. `test_endpoint.py` gains a `--rerank` option measuring p50/p95 for 25 pairs, 10 warm runs.

**Score parity and performance**

- [x] Score parity: the same 25 candidates × ≥ 20 dev questions, scored on local CPU and remote GPU. After the sigmoid the absolute difference is ≤ 1e-3 (fp32) and the top 5 ranking matches 100%. If not, stop and ask the owner (fp16 needs a different tolerance).
- [x] Warm rerank latency, compared with 15.7 s/question on CPU, recorded in section 5.
- [x] Warm TTFT and tokens/second of chat after shrinking the KV cache are no more than 10% worse than the A10 numbers before the change (A10, `gpu-memory-utilization` 0.90: warm TTFT 943 ms, 47.9 tokens/s, [V2-10](V2-10-ai-service-qa-pipeline.md) milestone 5 A).
- [x] (Moved from V2-10, owner settled 2026-11-09) Put FlashInfer's JIT cache (`~/.cache/flashinfer`, or the cache environment variable FlashInfer uses in vLLM 0.33.0) on a volume so a cold start does not rebuild the sampling module. Record the cold start time before and after (before: 264 s on A10).

**ai-service and eval**

- [x] `providers/rerank.py`: `RemoteRerankProvider` (`provider: modal`) calls `{providers.modal.base_url}/rerank` through httpx with a configurable timeout. HTTP errors, timeouts and bad JSON all become `RerankError`. Applies the same `_sigmoid`; empty `passages` make no network call. `build_rerank_provider` accepts `local | modal | none`.
- [x] `config/models.yaml` and `.env.example` declare the provider and timeout. The key is still `SOPILOT_LLM_API_KEY`; no new secret variable.
- [x] Unit tests with httpx `MockTransport`: success, `401`, timeout, a logit count different from the passage count, empty `passages`.
- [x] `eval/`: the rerank config accepts `provider: modal` and calls the same `RemoteRerankProvider`. Rerun RQ2/RQ2b on `sop-main` and `sop-main-v2`; the numbers match the old RQ2 within the parity tolerance. Results and latency recorded in section 5.

**Docs**

- [x] TECH-V2-ai-service §4.3/§6.4 (remote rerank provider, the `/v1/rerank` endpoint), ADR-006 §4.4 (rerank runs on the same Modal endpoint), `infrastructure/modal/README.md`. `check-docs.ps1` green.

---

## 3. Step-by-step implementation guide

### Step 0: Serving-option spike (≤ 1 GPU hour)
- **File:** a trial script in the scratchpad, not committed.
- Try two `@modal.web_server` (ports 8000 and 8001) on one `@app.cls` and confirm both URLs point at one container (one GPU, the same process id). If not, choose the FastAPI gateway.

### Step 1: Modal container
- **File:** `infrastructure/modal/serve_vllm.py` (MODIFY)
- The image adds `sentence-transformers`, the same version as ai-service. Pin revision `BAAI/bge-reranker-v2-m3` `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` (as in `eval/configs/rq2-rerank-bge-m3.yaml`). `download_model` also downloads the reranker into `sopilot-hf-cache`.
- Load `CrossEncoder(..., device="cuda", max_length=512)` first, then run vLLM. Keep `scaledown_window=60`, `max_containers=1`, `startup_timeout` 600 (watch the cold start).

### Step 2: Endpoint measurement
- **File:** `infrastructure/modal/test_endpoint.py` (MODIFY): `--rerank`, `--rerank-parity <pairs file>`.

### Step 3: ai-service provider
- **Files:** `services/ai-service/src/sopilot_ai/providers/rerank.py`, `providers/registry.py`, `config/models.yaml`, `.env.example` (MODIFY); `tests/unit/test_rerank_remote.py` (CREATE).

### Step 4: Harness
- **Files:** `eval/sopilot_eval/retrievers.py`, a new config `eval/configs/rq2-rerank-modal.yaml` (CREATE).

### Step 5: Docs and measurements
- Fill section 5, update TECH/ADR/README, update the PLAN.

---

## 4. Testing

| Test kind | Content | Command |
|---|---|---|
| Unit | `RemoteRerankProvider`: success, 401, timeout, mismatched logit count, empty; `build_rerank_provider` with the three providers | `./scripts/run-tests.ps1 -Scope ai-service -Type unit` |
| Build | ruff + compileall | `./scripts/validate-build.ps1 -Scope ai` |
| Eval | the existing harness tests green; the modal config runs | `cd eval; uv run pytest -q` |
| Manual (Modal) | `/v1/rerank` 200/401, CPU–GPU score parity, latency, chat TTFT after the VRAM change | `python infrastructure/modal/test_endpoint.py --rerank` |

---

## 5. Evidence

Measured on 2026-11-09, A10 GPU, `us-east` endpoint, from the owner's machine (Vietnam); client-side latency numbers include the network.

| Item | Result |
|---|---|
| Step 0 (spike) | Two `@modal.web_server` (8000, 8001) in one `@app.cls` create **one** `Svc.*` function with `max_containers=1`, two separate URLs but the same container. The spike ran on CPU; the app is stopped. **Consequence:** two different hosts, so rerank needs `SOPILOT_RERANK_BASE_URL` (the provider reads `providers.modal.rerank_base_url`), not `{base_url}/rerank` as the ticket said. No proxy and no `fastapi` needed (the rerank server uses the standard library's `http.server`). |
| Container | `Serve` (`serve_vllm.py`): `@modal.enter` loads the fp32 CrossEncoder on CUDA, then runs vLLM with `--gpu-memory-utilization 0.85`; `--max-model-len 8192` still starts. The image adds `sentence-transformers==6.2.0` (matching `uv.lock`). The chat URL is unchanged thanks to `label`. |
| VRAM | **Not recorded** per part: the logs of the measured container can no longer be retrieved. Only indirect evidence: vLLM starts and serves fine at 0.85 next to the reranker. |
| Cold start | 260 seconds (`/v1/models` with the container at 0), versus 494 seconds in V2-34 (two measurements under different conditions, not a strict comparison). |
| `/v1/rerank` | Missing key → `401`. 25 passages × 10 warm runs: p50 **1386 ms**, p95 1407 ms (`test_endpoint.py --rerank`). |
| Chat before/after | Before (A10, 15 questions): warm TTFT 949 ms, 46.6 tokens/second. After (0.85 + reranker): 841 ms, 47.2 tokens/second. Not more than 10% worse. |
| CPU–GPU score parity | 24 `sop-main` dev questions × 25 candidates (fp32): maximum sigmoid difference **2.7e-6** (threshold 1e-3); top 5 identical for **24/24** questions. Measured with two `run` passes (CPU `rq2-rerank-bge-m3.yaml`, GPU `rq2-rerank-modal.yaml`) comparing `per_question.jsonl`. `--rerank-parity` was not added to `test_endpoint.py` (the script has no sentence-transformers). |
| RQ2 `sop-main-v2` test (3 runs) | `hybrid` recall@5 0.835 / MRR 0.6714; `hybrid-rerank` **0.9525 / 0.9101**, identical to the old numbers (0.9525 / 0.9101). p50 per question **976 ms** (p95 1074 ms) versus 18,129 ms on CPU. Rankings stable across runs. |
| RQ2b `sop-main-v2` test | `dense` 0.9125 / 0.7926; `hybrid-legacy-w` 0.8725 / 0.7163; `dense-rerank` 0.9525 / 0.9115; `hybrid-legacy-w-rerank` 0.9575 / 0.9141: **identical to the old RQ2b numbers** on all four rows. Rerank p50 about 1.18 seconds versus 15.7 seconds. |
| RQ2 `sop-main` test | `hybrid` 0.9571 / 0.85; `hybrid-rerank-modal` 1.0 / 0.9726 (70 questions); no old numbers on the same set to compare. |
| Tests | `test_rerank_remote.py` 8 tests; ai-service unit 566 passed, 15 xfailed; `eval` pytest 120 passed, ruff green; `check-docs.ps1` green. |
| VRAM (addendum) | When vLLM reports `healthy`: `nvidia-smi` **21,180 / 23,028 MiB** (92%). The reranker process (torch): allocated 2.12 GiB, reserved 2.13 GiB. vLLM takes the rest (0.85 × 22.5 GiB ≈ 19.1 GiB for 10.3 GiB of weights, the KV cache and CUDA graphs). |
| FlashInfer cache | Volume `sopilot-flashinfer-cache` mounted at `/root/.cache/flashinfer`, committed after vLLM is ready. Two consecutive cold starts after deploy: first (build then save) **321 s**, second (load from the volume) **159 s**, versus 264 s before (V2-10 milestone 5 A). Log: vLLM `healthy` 133 s after the `enter` hook. |
| GPU cost | `modal billing report` on 2026-11-09: the current `sopilot-vllm` app $0.11 (20h) + $1.00 (21h) + $0.58 (22h) = **about $1.69** for the baseline measurements, deploy, parity, RQ2/RQ2b and the cold starts; downloading the reranker weights $0.007; the CPU spike $0.00004. Hours after 22h are not in the report yet (Modal only reports whole hours), including two cold starts and the FlashInfer cache check. |

**Findings while running:** (1) the container sleeps after 60 idle seconds, so once the harness has built the index the first rerank call hits a cold start (~260 seconds): the modal config's `timeout_s` is set to 600 seconds. (2) Modal returns `303` with a result URL when a request lasts longer than about 150 seconds; `RemoteRerankProvider` enables `follow_redirects` (tested). (3) `sop-main`/`sop-main-v2` chunks were sent to Modal as the ticket allows.

**Acceptance (owner, 2026-11-09):** `done`. `bge-reranker-v2-m3` reranking runs on the A10 GPU in the same container as vLLM: CPU–GPU score parity (maximum difference 2.7e-6, top 5 identical 24/24), RQ2 and RQ2b on `sop-main-v2` identical to the old numbers, warm rerank p50 about 1.0–1.4 s versus 15.7–18.1 s on CPU, chat no worse, VRAM 21,180 / 23,028 MiB, cold start 264 s → 159 s thanks to the FlashInfer cache. The owner accepts policy (a) on rerank failure (stop with `RerankError`, no fallback to hybrid). Accepted gaps: the GPU cost from 23h onward is not in the Modal report yet (about $1.69 recorded up to the end of 22h); the Docker integration tests were not run because no SQL changed. Choosing the default retrieval mode and tuning `thresholds.hybrid_rerank` still belong to `V2-10`/`V2-18`.

---

## 6. Quick check commands
```powershell
./scripts/validate-build.ps1 -Scope ai
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/check-docs.ps1
```
