---
id: V2-44
title: "ai-service: SetFit routing classifier behind the rules (shadow first)"
type: feat
status: todo # todo | in_progress | review | done | blocked
created: 2026-11-17
updated: 2026-11-17
author: "Owner"
scope: ai-qa
priority: P2
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-27]
blocks: [V2-18]
blocked_reason: ""
branch: "feat/ai-setfit-router"
refs:
  - docs/architecture/decisions/adr-012-setfit-routing-classifier.md
  - docs/architecture/components/ai-service.md
  - docs/handoffs/handoff-routing-classifier-2026-11-17.md
---

# TICKET V2-44: SetFit routing classifier behind the rules

> **Scope:** `ai-qa` | **Size:** `L` | **Priority:** `P2`. [ADR-012](../../../../architecture/decisions/adr-012-setfit-routing-classifier.md) is approved (2026-11-17); its open points are settled during this ticket.

## Context

[ADR-012](../../../../architecture/decisions/adr-012-setfit-routing-classifier.md) proposes replacing the embedding comparison of `SemanticLayer` (V2-27, TECH-V2-ai-service §7.1 step 3) with a SetFit classifier over `bge-m3`, in the `two_group+` design: the classifier predicts 14 labels, and five corpus-dependent labels (`off_topic`, `legal_medical`, `personal_data`, `abuse_with_question`, `about_source`) are left to retrieval. The experiment evidence (86 of 101 routed correctly, 0 costly errors on the frozen test split) and its limits are in the ADR §5. The experiment code lives in `eval/`; this ticket brings the classifier into the service.

## Acceptance criteria

- [ ] The open points of ADR-012 §4 (artifact location, the `about_source` template, `feedback_in_chat`) are decided with the owner and recorded in the ADR.
- [ ] The classifier artifact (`body/`, `head.npz`, label list, deferred set, input format) is declared in `config/models.yaml`; no model id or path is hard-coded in Python. The artifact is not committed; `services/ai-service/README.md` says how to obtain it.
- [ ] `qa/router.py` (or a module it imports) loads the body with `sentence-transformers` and applies `head.npz` with numpy; no `setfit` import at runtime. Probabilities match the eval run on a fixed set of questions (argmax identical, maximum difference below 0.001), as a unit test with a small fake head and a skip-marked test with the real artifact.
- [ ] Order: rules first, classifier second. Harmful content, PII and the guard stay rule-based; the classifier never produces `REFUSED_GUARD`.
- [ ] Deferred labels are never routed before retrieval. `off_topic` keeps its post-gate behaviour (`OUT_OF_SCOPE`, TECH §7.1 step 8); `legal_medical` and `personal_data` may still attach the existing disclaimer after generation. `sop_question` and `followup` always go to retrieval.
- [ ] A flag `SOPILOT_ROUTER_CLASSIFIER_MODE` with `off` (default, behaviour is exactly V2-27's), `shadow` and `on`. In `shadow` the prediction is recorded in `messages.route` (layer, label, confidence) and changes nothing. New variables are documented in `.env.example` with dummy values.
- [ ] The classifier receives the previous turn when there is one, in the same format as training (`Previous message: …\nCurrent message: …`), and the PII-masked text, never the raw question.
- [ ] Latency is measured on the owner's machine with the service running (p50 and p95 added by the step, resident memory), and recorded against the ADR figures (about 100 ms p50, 2.9 GB).
- [ ] History handling is checked on the service path. The model is trained with augmented history (ADR-012 §5: without it a previous message acts as a follow-up cue); the ticket decides which text of `ctx.history` is passed as the previous message (training used one short assistant sentence, without `[n]` markers) and the corpus-specific set reports accuracy for rows with and without history separately, including a fresh SOP question, a greeting and thanks after an answer.
- [ ] A corpus-specific routing test set (owner-reviewed, at least 100 questions from the owner's real corpus, not used for training or tuning) is built and scored. **Switching to `on` requires 0 costly errors on it**; otherwise the mode stays `shadow` and the reason is recorded.
- [ ] The corpus-specific test set also measures the **rule layer on its own**: the share of genuine `sop_question` / `followup` rows that the rules turn into `REFUSED_GUARD`, `TEMPLATE` or an abuse answer (ambiguous short forms such as `cc`, `dm`, `vl`, `cl` and the `inject.reveal_prompt` patterns are the known risks), reported separately from the classifier's errors. Target: 0 on the set; each hit is listed with its rule id.
- [ ] In `shadow` mode the route trace records both decisions (the rule layer's and the classifier's label and confidence), so they can be compared on real traffic before `on`.
- [ ] `eval/` reports the same numbers through the service code path (`eval/configs/routing-*.yaml`), not a copy of the logic.
- [ ] TECH-V2-ai-service §7.1 step 3 gets a dated note describing the classifier; no section is renumbered.
- [ ] No `print`, no logging of question text or model output; errors returned to clients are fixed text with a stable code.

## Implementation notes

- Reuse: `SemanticLayer` and `qa/router_thresholds.yaml` stay until `on` is accepted, so the flag can fall back to V2-27.
- The body is a fine-tuned copy of `bge-m3`; its vectors cannot be reused for retrieval, and retrieval vectors cannot feed the head. Budget a second encoder pass and about 2.9 GB of memory per process; load it lazily on the first question, as the service already does for the embedder.
- Training and the artifact are reproducible from `eval/experiments/routing/modal_setfit_app.py` and `eval/sopilot_eval/routing_setfit_remote.py --modal --with-history --save` (`uv run --with modal`, not a project dependency). Do not retrain on `test.jsonl`.
- Known confident errors to keep in the corpus test set: sarcastic SOP questions ("Tuyệt thật, quy định này …"), unaccented HR questions read as `legal_medical` or `personal_data`, `abuse_only` read as `about_bot`.
- Adding `sentence-transformers` to the service's runtime dependencies, if it is not already there, needs the owner's agreement (CLAUDE.md constraint 12).

## Verification

| Criterion | Command / test | Result |
|---|---|---|
| Unit tests, flag off equals V2-27 | `./scripts/run-tests.ps1 -Scope ai-service -Type unit` | filled in at review |
| Build and lint | `./scripts/validate-build.ps1 -Scope ai` | filled in at review |
| Eval harness unchanged | `cd eval; uv run pytest -q` | filled in at review |
| Corpus-specific test set, 0 costly | eval routing config for the service path | filled in at review |
| Docs | `./scripts/docs/check-docs.ps1` | filled in at review |

## Evidence

None yet. Required before `done`: the corpus-specific numbers, the latency and memory measurements and the owner's review.
