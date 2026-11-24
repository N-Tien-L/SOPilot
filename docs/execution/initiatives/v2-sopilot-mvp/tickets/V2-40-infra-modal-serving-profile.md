---
id: V2-40
title: "infra: implement ADR-011 serving profile (L40S, parallel eval, context budget)"
status: done
type: feat
created: 2026-11-16
updated: 2026-11-16
author: "Owner"
scope: infra
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-35]
blocks: [V2-18, V2-37]
branch: "feat/infra-modal-serving-profile"
assignee: pair
refs:
  - docs/architecture/decisions/adr-011-modal-serving-profiles.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/architecture/components/ai-service.md
---

# TICKET V2-40: Implement the ADR-011 serving profile

> **Scope:** `infra` (+ `eval`, `ai`) | **Size:** `L` | **Priority:** `P0`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `feat/infra-modal-serving-profile`

## 1. Context & goal
[ADR-011](../../../../architecture/decisions/adr-011-modal-serving-profiles.md) (owner decision 2026-11-15, amends ADR-006 §4.4) moves the answer model from one A10 to one L40S deploy with a 64K context for both eval and the demo. Its "Follow-up" list is not ticketed; nothing in it is implemented or measured, and every figure in the ADR is an *estimate*. This ticket implements the list and replaces the estimates with measurements. `V2-37` waits for it, because every reported answer-level run must use the L40S deploy (ADR-011 §2.2).

Dependencies `V2-10` and `V2-35` were `done` when work started (checked 2026-11-16).

## 2. Acceptance criteria
> **Owner decision 2026-11-16 (scope):** the full eval runs (the `multi_passage` group with the new budget and the dev-split eval at `--concurrency 8`) and the cost of one eval run are **deferred to `V2-37`**: the AI pipeline still has pending fixes, so running them now would spend Modal budget on an unfinalized pipeline. Criteria 3, 4 and 5 are ticked for what stayed in scope; the deferred parts are listed in the Evidence table and in `V2-37` §3.

The criteria are listed in the order the work is done. The context-budget values (§2.4 below) depend on the measured KV cache (§2.3), so they come after it.

1. - [x] **Server.** `infrastructure/modal/serve_vllm.py` uses GPU `L40S` and the flags of ADR-011 §2.1 (`--max-model-len 65536`, `--gpu-memory-utilization 0.85`, `--kv-cache-dtype auto`, `--max-num-seqs 8`, `--max-num-batched-tokens 16384`, `@modal.concurrent(max_inputs=8)`, `scaledown_window` about 300 s). The reranker stays in the same container with `torch.cuda.set_per_process_memory_fraction` so it cannot grow into vLLM's share. `infrastructure/modal/README.md` describes the profile and the warm-up procedure for the demo (ADR-011 §2.3). *Deployed 2026-11-16; the launch line in the Modal log carries the flags (ADR-011 §5).*
2. - [x] **Eval concurrency.** `eval/sopilot_eval/answers.py` takes `--concurrency` (default `1`, current behaviour). With N > 1 it sends up to N requests at once and writes `per_question.jsonl` in question order (a unit test: shuffled completion order, identical output). Quality metrics come from the concurrent run; latency and TTFT come from a separate run at concurrency 1 (`bench_context.py ttft`, synthetic prompts at fixed sizes; `answers.py` records no latency), and the report says which is which (`report.json` records `concurrency`). With N > 1 the harness raises its client-side rpm/tpm/timeout itself (review finding: the service defaults abort a concurrent run).
3. - [x] **Measurements replace estimates.** ADR-011 gets a measured-results section (appended, sections not renumbered): startup `GPU KV cache size`, VRAM with the reranker loaded, cold start (with and without the FlashInfer cache), TTFT at 8K/32K/64K prompts, decode tokens/s, cost of one test run. The "*estimate*" markers are replaced or kept with a reason. Tools: `infrastructure/modal/bench_context.py ttft` (TTFT and decode speed at chosen prompt sizes), `bench_thinking.py`, `test_endpoint.py`.
4. - [x] **Context budget.** `retrieval.context.max_tokens`, `context_k`, `section_max_tokens` and `SOPILOT_LLM_CONTEXT_MAX_TOKENS` in `services/ai-service/config/models.yaml` carry the values chosen for the 64K context, the same for eval and the demo (ADR-011 §2.4). Chosen **after** the measurements of criterion 3, with this rule, and the numbers recorded in the ADR:
   - 8 concurrent requests at the budget fit in the measured KV pool: `8 × (SOPILOT_LLM_CONTEXT_MAX_TOKENS + max output tokens) ≤ measured GPU KV cache size` (tokens);
   - the measured demo TTFT at that prompt size is at most **10 s** (proposed; the owner may change it).

   TECH-V2-ai-service and `services/ai-service/.env.example` say so; the `multi_passage` group of `answers.py` is run with them.
5. - [x] **No regression.** The pass line, all three required:
   - `bench_context.py smoke --concurrency 8 --tokens 32000`: 8 of 8 requests complete;
   - an eval run on the `dev` split with `answers.py --concurrency 8` finishes with no failed request (every row is an answer or a gate refusal) and the server log has no `preempt` / `OOM` / `out of memory` line (the check is a log search, recorded with the command);
   - `cd eval; uv run pytest -q` and the ai-service unit tests pass.

   **If the smoke or the eval run fails**, try in this order, one change at a time, re-run, and record each step and its result in ADR-011:
   1. lower `--max-num-seqs` and `@modal.concurrent(max_inputs=…)` to 4 and run eval with `--concurrency 4` (quality metrics do not depend on concurrency; only the wall-clock time grows);
   2. lower the context budget (criterion 4) so the KV rule holds, or lower `--max-model-len` to 32768;
   3. if neither is enough, stop and report to the owner: the ADR-011 premise (8 × 64K on one L40S) does not hold.
6. - [x] **Docs.** ADR-011 "Follow-up" items 1–4 marked done with links; PLAN change-log line.

## 3. Guide
- Open decision in ADR-011 §2.3 (MTP speculative decoding for the demo) stays out unless the owner decides it; if enabled, record that demo and eval configurations diverge.
- A100 is not an option here; H100 is only mentioned in the ADR as a comparison. Check Modal pricing at the time of the run before quoting cost.
- Modal spend is the owner's: ask before each deploy and before long eval runs. First cold start on L40S rebuilds the caches (about 320 s); warm it once after the switch.
- Do not mix A10 and L40S answer results in the thesis (ADR-011 §2.2).
- Commits, in order (one ticket, separate commits): `--concurrency` in the eval harness; the Modal profile and README; this ticket fix and `bench_context.py`; measurements and the ADR results section (needs a deploy); context-budget values and docs; status and evidence.

## 4. Testing
```powershell
cd eval; uv run pytest -q
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/docs/check-docs.ps1
```
Plus the measured runs against the deployed endpoint (not run in CI): `bench_context.py ttft`, `bench_context.py smoke`, and `answers.py --concurrency 8` on `dev`.

`eval/datasets/` and `datasets/` are gitignored: a fresh worktree has no copy and the eval suite then fails on missing data until they are copied from the main checkout.

## 5. Changed files
| Area | Action |
|---|---|
| `infrastructure/modal/serve_vllm.py`, `infrastructure/modal/README.md` | MODIFY |
| `infrastructure/modal/bench_thinking.py`, `infrastructure/modal/bench_context.py` | ADD |
| `eval/sopilot_eval/answers.py` and its tests | MODIFY |
| `services/ai-service/config/models.yaml`, `.env.example`, TECH-V2-ai-service | MODIFY |
| ADR-011 (measured results) | MODIFY |

## 6. Evidence
Recorded as the work is done; only real command output goes here.

| Criterion | Evidence |
|---|---|
| 2. Eval concurrency | `cd eval; uv run --extra dev pytest -q tests/test_answers.py`: 30 passed (6 new: order under shuffled completion, concurrent report equals sequential, failure cancels queued calls, a failure late in the list stops the queue, client limits are raised but never lowered, concurrency below 1 refused). Full eval suite with the ignored datasets copied in: 157 passed. Review by a fresh `v2-reviewer` (Opus): no blockers, 3 warnings (client TPM limit and timeout, rerank sharing the 8 slots, `k` source documented), all addressed in code or docs. |
| 1. Server | `modal deploy infrastructure/modal/serve_vllm.py` (profile `n-tien-l`) succeeded. The Modal log shows `vllm serve ... --max-model-len 65536 --kv-cache-dtype auto --max-num-seqs 8 --max-num-batched-tokens 16384 --gpu-memory-utilization 0.85`, `GPU KV cache size: 784,931 tokens`, GPU memory 41,130 of 46,068 MiB with the reranker loaded. |
| 3. Measurements | ADR-011 §5 holds KV cache size, VRAM, first-start time (268 s), the start with every cache warm (92 s to `/health` `200`, from timing `curl` on the unauthenticated `/health` after the container had idled 7 hours; vLLM healthy 73 s after the hook), TTFT at 8K/32K/64K (1.64 / 3.89 / 7.36 s median) and decode speed, from `bench_context.py ttft`. **Deferred to V2-37:** the cost of one eval run. |
| 5. No regression | `bench_context.py smoke --concurrency 8 --tokens 32000`: 8 of 8 completed in 25.4 s. Log of the L40S run: 0 `preempt`, 0 OOM, 0 tracebacks, 45 of 45 `200 OK`; KV usage peaked at 33.5%. **Deferred to V2-37:** the `dev` eval with `answers.py --concurrency 8`; the 8-at-once behaviour is covered by the smoke only. |
| 4. Context budget | Values set (owner choice "Moderate", 2026-11-16): `context_k` 8, `section_max_tokens` 3000, `context.max_tokens` 16000, `SOPILOT_LLM_CONTEXT_MAX_TOKENS` 60000, recorded in ADR-011 §5, `models.yaml`, TECH-V2-ai-service (config excerpt and env table), `.env.example`. `answers.py` now takes `k` from `models.yaml`. `cd services/ai-service; uv run --python 3.12 --extra dev pytest tests/unit -q`: 593 passed, 3 skipped, 15 xfailed; ruff clean; eval suite 155 passed. ai-service integration suite (Docker): 150 passed. **Deferred to V2-37:** the `multi_passage` run with these values. |
| 6. Docs | ADR-011 follow-up items 1–4 marked done (the eval-run parts deferred to V2-37 are stated there); PLAN status, counters and change log updated 2026-11-16. |
