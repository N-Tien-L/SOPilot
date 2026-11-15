---
id: V2-40
title: "infra: implement ADR-011 serving profile (L40S, parallel eval, context budget)"
type: feat
status: todo
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

## 2. Acceptance criteria
- [ ] **Server.** `infrastructure/modal/serve_vllm.py` uses GPU `L40S` and the flags of ADR-011 §2.1 (`--max-model-len 65536`, `--gpu-memory-utilization 0.85`, `--kv-cache-dtype auto`, `--max-num-seqs 8`, `--max-num-batched-tokens 16384`, `@modal.concurrent(max_inputs=8)`, `scaledown_window` about 300 s). The reranker stays in the same container with `torch.cuda.set_per_process_memory_fraction` so it cannot grow into vLLM's share. `infrastructure/modal/README.md` describes the profile and the warm-up procedure for the demo (ADR-011 §2.3).
- [ ] **Eval concurrency.** `eval/sopilot_eval/answers.py` takes `--concurrency` (default `1`, current behaviour). With N > 1 it sends up to N requests at once and writes `per_question.jsonl` in question order (a unit test: shuffled completion order, identical output). Quality metrics come from the concurrent run; latency and TTFT come from a separate run at concurrency 1 on a fixed sample, and the report says which is which.
- [ ] **Context budget.** `retrieval.context.max_tokens`, `context_k`, `section_max_tokens` and `SOPILOT_LLM_CONTEXT_MAX_TOKENS` in `services/ai-service/config/models.yaml` carry the values chosen for the 64K context, the same for eval and the demo (ADR-011 §2.4). TECH-V2-ai-service and `services/ai-service/.env.example` say so; the `multi_passage` group of `answers.py` is run with them.
- [ ] **Measurements replace estimates.** ADR-011 gets a measured-results section (appended, sections not renumbered): startup `GPU KV cache size`, VRAM with the reranker loaded, cold start (with and without the FlashInfer cache), TTFT at 8K/32K/64K prompts, decode tokens/s, cost of one test run. The "*estimate*" markers are replaced or kept with a reason. Tools: `infrastructure/modal/bench_thinking.py`, `infrastructure/modal/test_endpoint.py`.
- [ ] **No regression.** A smoke eval at concurrency 8 shows no OOM or preemption; the existing eval tests (`cd eval; uv run pytest -q`) and ai-service unit tests pass.
- [ ] **Docs.** ADR-011 "Follow-up" items 1–4 marked done with links; PLAN change-log line.

## 3. Guide
- Open decision in ADR-011 §2.3 (MTP speculative decoding for the demo) stays out unless the owner decides it; if enabled, record that demo and eval configurations diverge.
- A100 is not an option here; H100 is only mentioned in the ADR as a comparison. Check Modal pricing at the time of the run before quoting cost.
- Modal spend is the owner's: ask before each deploy and before long eval runs. First cold start on L40S rebuilds the caches (about 320 s); warm it once after the switch.
- Do not mix A10 and L40S answer results in the thesis (ADR-011 §2.2).

## 4. Testing
```powershell
cd eval; uv run pytest -q
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/docs/check-docs.ps1
```
Plus the measured runs against the deployed endpoint (not run in CI).

## 5. Changed files
| Area | Action |
|---|---|
| `infrastructure/modal/serve_vllm.py`, `infrastructure/modal/README.md` | MODIFY |
| `eval/sopilot_eval/answers.py` and its tests | MODIFY |
| `services/ai-service/config/models.yaml`, `.env.example`, TECH-V2-ai-service | MODIFY |
| ADR-011 (measured results) | MODIFY |
