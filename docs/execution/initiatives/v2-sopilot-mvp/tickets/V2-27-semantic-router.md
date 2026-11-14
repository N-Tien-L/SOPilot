---
id: V2-27
title: "ai-service: semantic router (rules + embedding) measured against rules only"
type: feat
status: done
created: 2026-10-20
updated: 2026-11-14
author: "Owner"
scope: ai-qa
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-05, V2-10]
blocks: [V2-18, V2-37]
branch: "feat/ai-qa-semantic-router"
assignee: pair
---

# TICKET V2-27: Semantic router and routing measurement

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
`V2-10` routes by rules (a VI/EN profanity dictionary, "strip then judge"). Rules miss unforeseen phrasings ("ê mày làm được gì vậy" (hey, what can you do), sarcastic insults). Owner decision 2026-10-20: use **rules + a semantic router**, rejecting an LLM classifier for the grey zone (extra latency, quota cost, instability, exposure to prompt injection). PRD-V2 FR-13 and ADR-006 §4.4 were updated for this decision.

The semantic router calls no LLM: it compares the question's embedding with each intent's example sentences, branches only when confident, and otherwise goes to RAG as before. The ticket has a runtime part and a measurement part (a: rules only, b: rules + router) to tune thresholds and produce numbers for the report.

## 2. Acceptance criteria
- [x] The router runs after the `V2-10` rules, only on questions the rules did not decide. Intents that branch: `greeting`, `thanks`, `about_bot`, `abuse_only` → a template, `outcome = TEMPLATE`, no LLM call, not counted against quotas. Truly harmful content is still blocked only by rules; the router blocks nothing.
- [ ] Changed 2026-10-21 (end-to-end audit by query type, owner decision D1; TECH-V2-ai-service §7.1): an extended router, **without an LLM classifier**. (a) `off_topic` does **not** branch before retrieval, because the router does not know what the corpus contains: only when the threshold gate has refused **and** the `off_topic` score exceeds the intent's threshold (and its `margin` over `sop_question`) is `refusal_reason = OUT_OF_SCOPE` assigned: the same refusal, without closest documents, not in the gap list; the router never changes a "let through" decision of the gate. (b) `action_request`, `personal_data`, `legal_medical` (rules plus router): still run RAG, only adding a fixed disclaimer in the question's language (`qa/templates.yaml`) before `citations`, recorded in `messages.checks.disclaimers`. (c) `about_source` (only with history): a template re-listing the previous turn's citations from `message_citations`, no LLM call. (d) `feedback_in_chat`: branches only when what remains after "strip" is empty; a template explaining how to click 👎. The router's decision is recorded in `messages.route` (`layer`, `intent`, `score`, `margin`).
- [x] Branching condition: the highest cosine ≥ the intent's own threshold **and** above the nearest `sop_question` example by at least `margin`. Otherwise → RAG. Thresholds and `margin` are configured in a file, not in code.
- [x] Embed the original question (not rewritten). For conversations without history, reuse that vector for dense retrieval; with history, retrieval embeds the rewritten question as before (one extra local embedding, no quota cost).
- [x] Example sentences are loaded at startup and embedded through `rag.embedding_cache`; when the active embedding model changes, the examples are re-embedded and vectors of two models are never compared.
- [ ] Switched by `SOPILOT_SEMANTIC_ROUTER_ENABLED`; when off the behaviour is exactly `V2-10`'s. Enabled by default after the thresholds are tuned on `dev`.
- [ ] A labelled routing dataset of 300–500 VI/EN questions, owner-reviewed, split into `dev`/`test`. Labels: `greeting`, `thanks`, `about_bot`, `abuse_only`, `abuse_with_question`, `harmful`, `followup` (with the previous turn), `sop_question`, `off_topic`; changed 2026-10-21 to add `action_request`, `personal_data`, `legal_medical`, `about_source` (with the previous turn), `feedback_in_chat`. Not overlapping `V2-10`'s guard set or the router's examples. Including teencode, no diacritics, sarcasm and cases easily misblocked without diacritics.
- [ ] A harness comparing (a) rules only with (b) rules + router on `test`, per label: precision/recall; the rate of `sop_question` wrongly routed to a template; the rate of `followup` sent into retrieval and then refused; the router's extra latency p50/p95; changed 2026-10-21 to add **the rate of out-of-scope (`off_topic`) questions leaking into the gap list** (target: `off_topic` questions refused by the gate get `OUT_OF_SCOPE` and stay out of the list) and the rate of `sop_question` wrongly labelled `OUT_OF_SCOPE`. Errors are classified **costly** (a business question misrouted, a `followup` refused) or **cheap** (a profane message leaking into RAG and then refused, a greeting getting "not found").
- [ ] Acceptance: (b) misroutes ≤ 2% of `sop_question` on `test` and adds no costly errors compared with (a). Otherwise keep `SOPILOT_SEMANTIC_ROUTER_ENABLED=false` by default and record why.
- [x] Report `docs/research/audit-routing-guard-eval-<date>.md`: embedding model and revision, the chosen thresholds, the (a) and (b) numbers, the decision on enabling by default.
- [x] Update TECH-V2-ai-service §7.1 step 3 (the router's position, configuration, vector reuse).
- [x] (Moved from V2-10, owner decision 2026-11-09; [V2-10](V2-10-ai-service-qa-pipeline.md) milestone 5 C) Consider the two points seen when running the `probe` group with the real model: 4/8 paraphrased attacks passed the loose threshold gate (0.456–0.504 versus 0.45), and an encoded (base64) answer does not match the fixed opening, so it becomes `ANSWERED` without citations. Rerun the 8 `probe` questions through router (b) and record the results.

## 2a. Evidence and open items (2026-11-13)
- Runtime: `qa/router.py` (`SemanticLayer`, thresholds and `margin` from `qa/router_thresholds.yaml`, examples in `qa/router_exemplars.yaml`), the `semantic_router` step (`conversations/steps.py`) wired into `QAService` when `SOPILOT_SEMANTIC_ROUTER_ENABLED=true`; examples cached in `rag.embedding_cache` by model/revision (`conversations/factory.py`). Details: TECH-V2-ai-service §7.1 step 3 (implementation note 2026-11-13).
- Tests: `tests/unit/test_router_semantic.py`, `tests/unit/test_qa_api_units.py` (with the router off the step chain is V2-10's; the flag defaults to `false`), `tests/integration/test_semantic_router_api.py` (9 tests, real Postgres). Eval: `eval/sopilot_eval/routing.py`, `eval/configs/routing-rules{,-router}.yaml`, `eval/tests/test_routing_eval.py`.
- Measurements on the draft dataset and `probe`: [AUDIT-routing-guard-eval-2026-11-13](../../../../research/audit-routing-guard-eval-2026-11-13.md) (`draft`). `test`: `sop_question` misrouted 0/53, costly errors 0 versus 0, cheap errors 59 → 43, router p50 102 ms / p95 121 ms; 0/8 `probe` questions routed.
- **The flag stays `false`**: the passing numbers exist only on an unreviewed dataset and examples; 0/53 gives only a 95% upper bound of about 5.7%, which does not prove ≤ 2%.
- **Still open:** (1) owner review of the 390-question set (`eval/datasets/routing/`, gitignored, including 71 questions prefixed "Please tell me:") and the examples; decide whether to commit the set (blocked by `datasets/` in `.gitignore`); (2) tune the thresholds on `dev`, rerun `test`, decide on enabling by default; (3) `feedback_in_chat` does not branch yet (needs the owner to decide how to detect "the rest is empty"); (4) measure `followup` through `qa/pipeline.py` (needs `evidence` for the `followup` questions); (5) owner review.

## 3. Guide
- **Runtime files:** `services/ai-service/src/qa/router.py` (an embedding layer after the rule layer), `qa/router_exemplars.yaml` (example sentences by intent, including `sop_question` as the control class), `qa/router_thresholds.yaml`.
- **Eval files:** `eval/sopilot_eval/routing.py`, `eval/configs/routing-{rules,rules-router}.yaml`, the dataset in `eval/datasets/routing/`. The harness calls `qa/router.py` directly and does not copy rules or examples into the harness.
- Examples may be generated by an LLM, but the owner reviews them before use. The `sop_question` examples and dataset questions come from the `V2-06` question set if available; otherwise written by hand and owner-reviewed.
- `followup` is only measured, never branched on: the question-rewrite step already handles follow-ups. If the share of refused `followup` is high, record it in the report to open a separate ticket. Changed 2026-10-21 (audit by query type): the metric "`followup` sent into retrieval and then refused" **cannot be measured with `qa/router.py` alone**, because it needs an LLM rewrite plus retrieval on a corpus tied to the previous turn. Each `followup` question in the dataset has a `previous_turn` and `corpus`/`evidence` pointing to the V2-06 corpus; this measurement runs through `qa/pipeline.py` (a real or fixed LLM rewrite, retrieval on that corpus) and records three outcomes separately: retrieved correctly, refused, and a follow-up-rule template asking back (TECH-V2-ai-service §7.1 step 4). The other metrics still run directly on `qa/router.py`.
- `abuse_only` messages recognized by the router record `guard_events(INPUT_FLAG)` with `rule_id = router.abuse`.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | threshold + `margin` condition, router off behaves like `V2-10`, vector reuse without history, examples re-embedded when the model changes | `uv run pytest tests/unit` in `services/ai-service/` |
| Unit | per-label metrics, costly/cheap error classification | `uv run pytest` in `eval/` |
| Manual | run (a) and (b) on `test`, attach `report.md` to the report | `python -m sopilot_eval.routing --config eval/configs/routing-rules-router.yaml` |
