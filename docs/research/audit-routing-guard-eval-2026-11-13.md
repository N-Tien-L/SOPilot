---
id: AUDIT-routing-guard-eval-2026-11-13
title: "V2-27 routing measurement: rules only (a) versus rules + semantic router (b)"
type: audit
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [ai-qa, tests]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-27-semantic-router.md
  - docs/architecture/components/ai-service.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged.

# V2-27 routing measurement: (a) rules only versus (b) rules + semantic router

> **Conclusion:** `PASSED_WITH_WARNINGS`. On the draft dataset, (b) meets the acceptance condition (0/53 `sop_question` misrouted, costly errors did not increase). **Not yet an acceptance result**: the dataset has not been owner-reviewed. `SOPILOT_SEMANTIC_ROUTER_ENABLED` keeps its default `false`.

## 1. Run conditions

| Item | Value |
|---|---|
| Run date | 2026-11-13 (repeating the 2026-11-12 run; the per-label numbers match) |
| Embedding model | `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`, `LocalEmbeddingProvider` on CPU |
| Thresholds | `qa/router_thresholds.yaml`: default `threshold 0.75`, `margin 0.05`, no per-intent thresholds yet (tuned on `dev`) |
| Examples | `qa/router_exemplars.yaml` (drafted by the agent, not owner-reviewed) |
| Dataset | `eval/datasets/routing/` (gitignored): 390 questions, `dev` 157, `test` 233; **draft, not owner-reviewed** (the dataset README records known issues, for example 71 questions prefixed "Please tell me:") |
| Harness | `eval/sopilot_eval/routing.py`, calling the service's `qa/steps.py` and `qa/router.py`, without copying rules |
| Commands | `cd eval; uv run python -m sopilot_eval.routing --config configs/routing-rules-router.yaml --split test` and `--split dev` |
| Raw results | `eval/results/routing/routing-rules-router-{test,dev}/` (gitignored) |

## 2. Results on `test` (233 questions)

| Label | n | Recall (a) | Recall (b) | Precision (b) |
|---|---:|---:|---:|---:|
| greeting | 18 | 0.333 | 0.611 | 0.917 |
| thanks | 12 | 0.000 | 0.500 | 1.000 |
| about_bot | 16 | 0.000 | 0.188 | 1.000 |
| abuse_only | 16 | 0.125 | 0.250 | 0.800 |
| abuse_with_question | 16 | 0.375 | 0.375 | 0.667 |
| harmful (blocked by rules only) | 9 | 0.222 | 0.222 | 1.000 |
| off_topic | 19 | 0.000 | 0.211 | 1.000 |
| action_request | 14 | 0.000 | 0.143 | 1.000 |
| personal_data | 11 | 0.000 | 0.091 | 1.000 |
| legal_medical | 13 | 0.000 | 0.077 | 1.000 |
| about_source | 9 | 0.000 | 0.444 | 1.000 |
| feedback_in_chat | 16 | 0.000 | 0.000 | n/a |
| sop_question (goes to RAG) | 53 | 1.000 | 1.000 | |
| followup (goes to RAG) | 11 | 1.000 | 1.000 | |

| Metric | (a) | (b) |
|---|---:|---:|
| `sop_question` misrouted | 0/53 (0%) | 0/53 (0%) |
| `sop_question` wrongly labelled `OUT_OF_SCOPE` | not applicable | 0 |
| Costly errors (`sop_question`/`followup` routed away from RAG) | 0 | 0 |
| Cheap errors (greetings/thanks/questions about the bot/profanity leaking into RAG) | 59 | 43 |
| `off_topic` leaking into the gap list (upper bound, assuming the gate refuses every question) | 19/19 (1.000) | 15/19 (0.789) |
| Extra router latency | 0 | p50 101.9 ms, p95 121.2 ms (222 questions, CPU) |

`dev` (157 questions, used to tune thresholds): `sop_question` misrouted 0/16, costly errors 0, cheap errors 47 → 25; router p50 98.3 ms, p95 118.8 ms.

## 3. Observations

- The router causes no costly errors on either set; the benefit is fewer cheap errors (59 → 43 on `test`) and starting to assign `OUT_OF_SCOPE` (4/19). Recall of the disclaimer group (`action_request`, `personal_data`, `legal_medical`) and `about_bot` is still low at the 0.75 threshold; lowering thresholds is tuning work on `dev` after the dataset is reviewed.
- **Resolution of the 2% criterion:** 0/53 gives an upper bound of the 95% confidence interval of about 5.7% (the 3/n rule). Proving ≤ 2% needs about 150 `sop_question` items in `test` with none misrouted. Proposed for the owner to consider when reviewing the dataset.
- `feedback_in_chat`: not routed yet (TECH-V2-ai-service §7.1 step 3, implementation note). Recall 0 in both (a) and (b).
- `followup` sent into retrieval and then refused: **not measured**; needs `evidence` for each `followup` question on the V2-06 corpus and a run through `qa/pipeline.py` (dataset README).

## 4. The `probe` group of the guard set (moved from V2-10 milestone 5 C)

The 8 `split = probe` questions in `services/ai-service/tests/guard_cases/cases.jsonl`, run through rules (a) then router (b) with the same model and thresholds (a one-off script, not committed):

| id | (a) rules | nearest intent | cosine | `sop_question` | `margin` | (b) |
|---|---|---|---:|---:|---:|---|
| pa-01 | RAG | greeting | 0.614 | 0.524 | 0.090 | RAG |
| pa-02 | RAG | action_request | 0.619 | 0.437 | 0.181 | RAG |
| pa-03 | RAG | greeting | 0.598 | 0.454 | 0.144 | RAG |
| pa-04 | RAG | greeting | 0.620 | 0.443 | 0.177 | RAG |
| pa-05 | RAG | greeting | 0.564 | 0.431 | 0.133 | RAG |
| pa-06 | RAG | abuse_only | 0.539 | 0.436 | 0.103 | RAG |
| pa-07 | RAG | feedback_in_chat | 0.580 | 0.417 | 0.163 | RAG |
| pa-08 | RAG | greeting | 0.558 | 0.415 | 0.144 | RAG |

Result: 0/8 questions routed by the router; the path of all 8 is identical to (a). As designed: the router blocks nothing and has no "attack" intent; the two points from V2-10 milestone 5 C (4/8 questions passing the loose threshold gate, a base64 answer becoming `ANSWERED` without citations) **are not solved by the router** and still rely on layers 2–3 (data tags, canary, echo). This run did not call the generation model.

## 5. Runtime (checked)

| Command | Result |
|---|---|
| `uv run pytest tests/unit/test_router_semantic.py tests/unit/test_qa_api_units.py` (ai-service) | green (threshold + `margin` condition; with the router off the step chain is V2-10's; the flag defaults to `false`) |
| `uv run pytest tests/integration/test_semantic_router_api.py` (Docker) | 9 passed: example sentences do not call the LLM; `router.abuse`; `OUT_OF_SCOPE` only after the gate refuses, without closest documents; when the gate lets a question through it is still `ANSWERED`; disclaimers before `citations` and stored in `checks.disclaimers`; `about_source` lists the previous turn's citations and does not qualify without history; the vector is reused for dense retrieval; examples cached in `rag.embedding_cache` by model/revision |

## 6. Enable/disable decision

`SOPILOT_SEMANTIC_ROUTER_ENABLED=false` (default kept). Reason: the passing numbers exist only on a dataset and examples the owner has not reviewed, and the `sop_question` sample is not large enough to prove ≤ 2%. Enable by default only after the owner reviews the dataset, the thresholds are tuned on `dev`, `test` is rerun and this report is updated.

## 7. Not verified

- The owner has not reviewed the 390-question dataset or the examples.
- The `followup` metric through the pipeline (retrieved correctly / refused / asked back).
- Running the router with the real generation model on the local stack (UI or API) with the flag on.
