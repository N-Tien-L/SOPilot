# Modal LLM Endpoint (vLLM on an L40S GPU)

> **Tickets:** `V2-34`, `V2-35`, `V2-40` | **Scope:** `infra` | **Parent plan:** `PLAN-V2-SOPILOT-MVP`
> **Decisions:** [ADR-011](../../docs/architecture/decisions/adr-011-modal-serving-profiles.md) (serving profile), [ADR-006 §4.4](../../docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md) (providers) | **Design:** [TECH-V2-ai-service §4.2, §4.3](../../docs/architecture/components/ai-service.md)

Deployment and test scripts for the OpenAI-compatible endpoint that serves the open model **Qwen3.5-9B** (FP8) with **vLLM** on **Modal**, plus the `bge-reranker-v2-m3` reranker in the same container.

---

## 1. Goals and constraints

1. **Independent of the service:** the deployment code lives outside `services/ai-service` and does not touch its `pyproject.toml`.
2. **Standard interface:** OpenAI-compatible `/v1/chat/completions` and `/v1/models`, consumed over HTTP by `services/ai-service/src/sopilot_ai/providers/llm.py`.
3. **Cost control:**
   - Modal **Starter** plan ($30 of free compute credits per month).
   - GPU **NVIDIA L40S** (48 GB, about $1.95 per hour; check Modal's Pricing page before quoting a cost). It replaced the A10 under ADR-011 for faster prefill on long prompts and native FP8 (W8A8; the A10 ran weight-only W8A16). **Results from the two GPUs are not mixed in the thesis.**
   - **Scale-to-zero** after 300 s idle (`scaledown_window`), long enough that a dev run and a test run back to back do not cold-start twice.
   - One container at most (`max_containers=1`): beyond 8 concurrent requests (`@modal.concurrent(max_inputs=8)`) requests queue in Modal instead of booting a second GPU container.
   - No pinned region (avoids the ×1.15–1.75 surcharge), not non-preemptible.
   - Model weights and compile caches live in `modal.Volume`s (`sopilot-hf-cache`, `sopilot-vllm-cache`, `sopilot-flashinfer-cache`) to shorten cold starts.
4. **Data and secrets:**
   - Never commit a real URL or API key.
   - Every prompt sent to Modal leaves the local machine: use sample data or `sop-main` only, never real internal documents.
   - **Accounts:** the project uses two Starter accounts, each with its own payment card (owner decision 2026-11-09, V2-10). Each account deploys and holds its own secret; the URL changes with the workspace name.

---

## 2. Serving profile (ADR-011 §2.1)

One configuration for eval and for the demo. The values are constants at the top of [`serve_vllm.py`](serve_vllm.py); the reasons are in the ADR.

| Setting | Value |
|---|---|
| GPU | `L40S` |
| `--max-model-len` | `65536` |
| `--gpu-memory-utilization` | `0.85` (the reranker lives in the rest) |
| `--kv-cache-dtype` | `auto` (bf16) |
| `--max-num-seqs` / `@modal.concurrent` | `8` / `8` |
| `--max-num-batched-tokens` | `16384` (chunked prefill) |
| `scaledown_window` | `300` s |
| Reranker memory | `torch.cuda.set_per_process_memory_fraction`, capped at `RERANK_GPU_MEMORY_GIB` (4 GiB) so its allocator cannot grow into vLLM's share |

The ai-service must build prompts that fit this context: `retrieval.context.*` and `SOPILOT_LLM_CONTEXT_MAX_TOKENS` in `services/ai-service/config/models.yaml` (ADR-011 §2.4).

---

## 3. Deployment

### Step 1: install the Modal CLI and log in
```bash
pip install modal
modal setup
```

### Step 2: create the API-key secret
```bash
# Replace <YOUR_RANDOM_SECRET_KEY> with a random secret string
modal secret create sopilot-vllm-secret VLLM_API_KEY="<YOUR_RANDOM_SECRET_KEY>"
```
The secret must define `VLLM_API_KEY`. If the secret or the key is missing, `modal deploy` is rejected and the container does not start: the endpoint never runs without authentication.

Set a budget alert for the Modal workspace on the dashboard (Settings → Usage/Billing) before the first deploy.

### Step 3: (optional) pre-download the weights
So the first start does not time out on the download:
```bash
modal run infrastructure/modal/serve_vllm.py::download_model
```

### Step 4: deploy
```bash
modal deploy infrastructure/modal/serve_vllm.py
```
Modal then returns public URLs of the form:
```
https://<workspace-name>--sopilot-vllm-serve.modal.run
```

**Modal spend is the owner's:** every deploy and every long eval run is the owner's call (ticket V2-40).

### Reranker in the same container (V2-35)

`serve_vllm.py` is an `@app.cls` (`Serve`): `@modal.enter` loads `bge-reranker-v2-m3` (CrossEncoder, CUDA, fp32, `max_length=512`, pinned revision), caps its PyTorch memory, then starts vLLM. Two `@modal.web_server`s share one container and one GPU, with two URLs:

```
https://<workspace-name>--sopilot-vllm-serve.modal.run    # /v1/chat/completions, /v1/models
https://<workspace-name>--sopilot-vllm-rerank.modal.run   # POST /v1/rerank
```

`POST /v1/rerank` takes `{"query": str, "passages": [str]}` (at most 64 passages) and returns `{"logits": [float]}` in the same order; the Bearer token is `VLLM_API_KEY`, and a missing or wrong one returns `401`. Run `modal run infrastructure/modal/serve_vllm.py::download_model` once to put the reranker weights on the volume. Check it with `python infrastructure/modal/test_endpoint.py --rerank` (needs `SOPILOT_RERANK_BASE_URL`).

---

## 4. Warm-up

A cold start takes about 160 s when the FlashInfer cache is on its volume and about 320 s the first time (ADR-011 §1; being re-measured on L40S under V2-40). That is longer than the ai-service's 30 s rerank timeout and its 120 s answer timeout, so warm the container before a run.

- **After switching GPU type (once):** the first start on L40S rebuilds the FlashInfer and `torch.compile` caches. Send one request and wait for it; later starts reuse the volumes.
- **Before an eval run:** send one request (for example `python infrastructure/modal/test_endpoint.py ...`) and wait for the answer. The 300 s `scaledown_window` then covers back-to-back runs.
- **Before the demo (ADR-011 §2.3):** about 10 minutes ahead, keep one container up with a longer idle window, then restore scale-to-zero afterwards. A warm hour costs about $1.95.

  ```python
  import modal

  serve = modal.Cls.from_name("sopilot-vllm", "Serve")()
  serve.update_autoscaler(min_containers=1, scaledown_window=900)   # before the session
  serve.update_autoscaler(min_containers=0, scaledown_window=300)   # afterwards
  ```
  `update_autoscaler` exists on class instances in the installed client (modal 1.4.2, checked by introspection, not yet run against a deploy). After any redeploy, check that the autoscaler values are the ones in `serve_vllm.py` and re-apply the demo values if they are not.
- Prepare 3–5 demo questions that need several SOP pages and run them before the session: a 9B model can miss evidence in the middle of a long prompt.

---

## 5. Testing and measuring the endpoint

For a **cold** TTFT, wait for the container to scale to zero (more than 300 s without a request; see `modal app list` or the dashboard), then run the script: the first query is then the cold one. The default per-request timeout is 900 s (`--timeout`) to wait out a cold start.

[`test_endpoint.py`](test_endpoint.py) checks:
- `/v1/models` and `/v1/chat/completions` respond.
- Time to first token (**TTFT**), cold and warm.
- Generation speed (**tokens/second**).
- The `enable_thinking=false` flag (the model closes the `<think>` tag from the prompt).

```bash
python infrastructure/modal/test_endpoint.py \
  --base-url "https://<workspace-name>--sopilot-vllm-serve.modal.run/v1" \
  --api-key "<YOUR_RANDOM_SECRET_KEY>" \
  --model "Qwen/Qwen3.5-9B" \
  --benchmark
```

[`bench_thinking.py`](bench_thinking.py) compares thinking on and off with the production prompt (run from `services/ai-service`; see its docstring).

Or by hand with `curl`:
```bash
# 1. List the models
curl -X GET "https://<workspace-name>--sopilot-vllm-serve.modal.run/v1/models" \
  -H "Authorization: Bearer <YOUR_RANDOM_SECRET_KEY>"

# 2. Send a question
curl -X POST "https://<workspace-name>--sopilot-vllm-serve.modal.run/v1/chat/completions" \
  -H "Authorization: Bearer <YOUR_RANDOM_SECRET_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [{"role": "user", "content": "Quy trình nghỉ phép của công ty gồm các bước nào?"}],
    "temperature": 0.0,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

---

## 6. Configuration for SOPilot V2 (`services/ai-service`)

Once the endpoint works, update `services/ai-service/.env` (copied from `services/ai-service/.env.example`):

```dotenv
# --- ai-service answer LLM (V2-10, ADR-006 §4.4, ADR-011) ---
SOPILOT_LLM_BASE_URL=https://<workspace-name>--sopilot-vllm-serve.modal.run/v1
SOPILOT_LLM_MODEL=Qwen/Qwen3.5-9B
SOPILOT_LLM_API_KEY=<YOUR_RANDOM_SECRET_KEY>
# Rerank on the GPU (V2-35); same key, different URL. Enable with RERANK_ENABLED=true, RERANK_PROVIDER=modal
SOPILOT_RERANK_BASE_URL=https://<workspace-name>--sopilot-vllm-rerank.modal.run/v1
SOPILOT_LLM_RPM=60
SOPILOT_LLM_TPM=200000
# Prompt ceiling under the served context of 65536 (ADR-011 §2.4, measured in §5)
SOPILOT_LLM_CONTEXT_MAX_TOKENS=60000
```

Then validate with:
```powershell
./scripts/check-env.ps1
```
