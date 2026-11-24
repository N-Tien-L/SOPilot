---
id: V2-43
title: "ai-service: an answer that ends inside the reasoning is stored as an empty ANSWERED"
type: fix
status: done
created: 2026-11-17
updated: 2026-11-17
author: "Owner"
scope: ai-qa
priority: P0
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-42]
blocks: [V2-17]
branch: "fix/ai-empty-answer-budget"
assignee: pair
refs:
  - docs/architecture/components/ai-service.md
  - docs/architecture/decisions/adr-011-modal-serving-profiles.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-17-parity-and-legacy-removal.md
---

# TICKET V2-43: Empty answer when the reasoning uses up the output budget

> **Scope:** `ai-qa` | **Size:** `S` | **Priority:** `P0`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `fix/ai-empty-answer-budget`

## 1. Context & goal
Found by a V2-17 parity driver run (2026-11-17, throwaway compose stack, Modal answer model with thinking on), UC-04 / FR-11: one owner question streamed `meta`, 1,366 `reasoning` events, `reasoning_done`, `done` and no `delta` or `citations`. The turn was stored as outcome `ANSWERED` with an empty `finalText`. The reasoning stopped mid-word with no `</think>`. Passing runs of the same driver had 742–1,500 reasoning events and up to 404 deltas. The failure is intermittent.

**Cause (confirmed from the code).**
1. *Budget.* `services/ai-service/config/models.yaml` set `llm.generate.max_output_tokens` to `${SOPILOT_LLM_MAX_OUTPUT_TOKENS:3000}`, sent as `max_tokens` (`providers/llm.py` `_body`). With `enable_thinking` on, the reasoning and the answer share those 3,000 tokens, and a long reasoning used all of them. `docker-compose.yml` does not pass `SOPILOT_LLM_MAX_OUTPUT_TOKENS`, `SOPILOT_LLM_CONTEXT_MAX_TOKENS` or `SOPILOT_LLM_THINKING` to `ai-service`, so the compose stack always runs on the `models.yaml` defaults.
2. *No detection.* `OpenAICompatibleLLM.stream` ignored `finish_reason`; `GenerateStep.run` (`conversations/steps.py`) returned `CONTINUE` with an empty `answer_text` when only `Thought` deltas arrived; `QAService._outcome` maps every `CONTINUE` to `ANSWERED`.

Goal: an answer has room for its reasoning, and a generation with no answer text is never streamed or stored as `ANSWERED`.

## 2. Acceptance criteria
- [x] **Budget.** `max_output_tokens` default 8192 and the `generate` chain's `context_max_tokens` default 57000 (57,000 + 8,192 = 65,192 ≤ 65,536 served; KV rule 8 × 65,192 = 521,536 ≤ 784,931, ADR-011 §5). `services/ai-service/.env.example`, `services/ai-service/README.md` and `infrastructure/modal/README.md` match. A `services/ai-service/.env` copied before V2-43 still sets `SOPILOT_LLM_MAX_OUTPUT_TOKENS=3000` and `SOPILOT_LLM_CONTEXT_MAX_TOKENS=60000` (a set variable wins over the `models.yaml` default, and an empty value means "no ceiling"): the owner updates both lines, or deletes them, before running ai-service from source. Compose does not pass these variables, so it always uses the defaults.
- [x] **Guard.** When the stream ends and the answer text is empty or whitespace, the turn ends as `outcome = ERROR` with the existing stable code `LLM_UNAVAILABLE` (SSE `error` with the `error_llm_unavailable` template text, quota turn refunded as for every `ERROR`), `checks.emptyAnswer = true`, and a structlog `answer_empty` event (`reasoning_chars`, `model`; no text, no tokens).
- [x] **Truncation visible.** The provider reads `finish_reason`; `"length"` logs `llm_output_truncated` (`provider`, `model`, `max_tokens`).
- [x] **No regression.** Normal answers stay `ANSWERED`; refusals are untouched; the ai-service unit suite and ruff pass.
- [x] **Live.** Re-run the UC-04 driver on the parity stack at least 3 times (intermittent): every answerable question sends `delta` and `citations`, or ends with `error LLM_UNAVAILABLE`, never an empty `ANSWERED`.
- [x] Owner review; then V2-17 re-runs UC-04 and FR-11 on `develop` after the merge.

## 3. Guide
- Code: `services/ai-service/config/models.yaml` (`llm.generate`), `providers/llm.py` (`stream`, `_delta_parts`), `conversations/steps.py` (`GenerateStep.run`).
- The client sees the same fixed text as for an unreachable model ("The answering service is not available. Please try again in a few minutes."): retrying is the right action, and no new code or template is needed.
- Not in this ticket: passing the `SOPILOT_LLM_*` budget variables through `docker-compose.yml` (a compose edit needs the owner's prompt; the `models.yaml` defaults now fit), the `rewrite` chain's `context_max_tokens` default (60000; its output is 200 tokens), and carrying `finish_reason` from the provider to `GenerateStep` (the two log events are correlated by time; the guard does not need it). Known limit: a `length` cut that arrives **after** some answer text still ends `ANSWERED` with a cut-off answer; only `llm_output_truncated` in the log shows it.

## 4. Testing
```powershell
./scripts/validate-build.ps1 -Scope ai
./scripts/run-tests.ps1 -Scope ai-service -Type unit
cd eval; uv sync --extra dev; uv run pytest -q
uv run --no-project --with pyyaml python eval/sopilot_eval/plan_check.py
./scripts/docs/check-docs.ps1
```

## 5. Changed files
| Area | Action |
|---|---|
| `services/ai-service/config/models.yaml`, `services/ai-service/.env.example` | MODIFY (8192 output, 57000 prompt ceiling, comments) |
| `services/ai-service/src/sopilot_ai/providers/llm.py` | MODIFY (`_delta_parts` returns `finish_reason`; `llm_output_truncated` log) |
| `services/ai-service/src/sopilot_ai/conversations/steps.py` | MODIFY (empty answer → `ERROR` / `LLM_UNAVAILABLE`, `answer_empty` log) |
| `services/ai-service/tests/unit/test_generate_step.py` | NEW (four behaviour tests) |
| `services/ai-service/tests/unit/test_llm_provider.py`, `tests/unit/test_qa_api_units.py` | MODIFY (finish_reason test; new defaults) |
| PLAN (`total_tickets`, DAG, tables, change log), `depends_on`/`blocks` of V2-10, V2-17, V2-42; `eval/tests/test_review_regressions.py` (pinned ticket count 42 → 43) | MODIFY |
| ADR-011 §5 (dated note), TECH-V2-ai-service (§4.2 excerpt, §7.4 rule, settings table) | MODIFY |

## 6. Results
Implemented on `fix/ai-empty-answer-budget` (from `develop` 25e83cb) and committed 2026-11-17; merged into `develop` (`61a44fd`) and into `chore/infra-remove-legacy` (`b6e0b80`); not pushed. **Status `done` (owner decision 2026-11-17: mark done after a clean review).**

**Tests added.** `test_a_stream_of_only_reasoning_ends_as_an_error_not_answered`, `test_a_stream_with_no_deltas_at_all_ends_as_an_error`, `test_a_whitespace_only_answer_after_reasoning_is_not_an_answer`, `test_reasoning_followed_by_answer_text_is_still_answered` (`test_generate_step.py`), `test_the_finish_reason_of_an_event_is_read_so_a_length_cut_can_be_seen` (`test_llm_provider.py`).

**Evidence.**
- `./scripts/validate-build.ps1 -Scope ai`: "All checks passed!", "Validation successful for scope ai."
- `./scripts/run-tests.ps1 -Scope ai-service -Type unit`: "621 passed, 1 skipped, 15 xfailed, 6 warnings", "All tests passed for ai-service". One earlier run of the same suite printed a Windows "access violation" thread dump from Docling's PDF pipeline threads; the rerun was clean, and no changed code touches Docling.
- `cd eval; uv run pytest -q`: "23 failed, 134 passed". All 23 are `FileNotFoundError` / missing-file asserts on the gitignored `eval/datasets` and `datasets/extraction`, absent in a fresh worktree (the same 23 as recorded in V2-42 §6). The pinned-count test `test_v2_plan_all_frontmatter_counters_dag_and_handover_match`: "1 passed".
- `uv run --no-project --with pyyaml python eval/sopilot_eval/plan_check.py`: `"tickets": 43`, `"edges": 110`, `"counters_match": true`, `"acyclic": true`, `"handover_covers_all_tickets": true`.
- `./scripts/docs/check-docs.ps1`: "docs check passed (13 warnings)" (all warnings are links to gitignored dataset paths in older docs).

**Review (`v2-reviewer`, 2026-11-17).** No blocker. Fixed: the stale `SOPILOT_LLM_CONTEXT_MAX_TOKENS=60000` in `infrastructure/modal/README.md` (60,000 + 8,192 > 65,536) and the `default 3000` in `services/ai-service/README.md`; the from-source `.env` step and the "cut after some answer text" limit are now in §2 and §3. Not changed (suggestions): the tests call `QAService._outcome` directly, with no integration test through `ask` (the existing `ERROR` path sends `error`, no `done`, stores `ERROR` and refunds quota, checked by reading); a whitespace-only answer from a scripted chain is still sent as a `delta` before the error (unreachable through the real provider, whose splitter strips leading whitespace). Pre-existing mismatch, reported and not aligned: TECH-V2-ai-service §4.2 shows `enable_thinking: false` for `generate`; `models.yaml` has `${SOPILOT_LLM_THINKING:true}`.

**Live re-run (2026-11-17).** The throwaway `sopilot-parity` stack's `ai-service` was rebuilt from `chore/infra-remove-legacy` at `b6e0b80` (V2-43 merged; the container's `models.yaml` shows `max_output_tokens: ${SOPILOT_LLM_MAX_OUTPUT_TOKENS:8192}` and `context_max_tokens: "${SOPILOT_LLM_CONTEXT_MAX_TOKENS:57000}"`; rerank on, Modal). The parity driver (`-QaOnly`) ran 3 times:

| Run | UC-04 owner question | UC-10 engineer | UC-10 HR, UC-05 |
|---|---|---|---|
| 1 | 1,791 `reasoning`, 279 `delta`, `citations`, `ANSWERED` | 976 `reasoning`, `ANSWERED`, cites the restricted SOP | `REFUSED_NO_EVIDENCE`, nothing of the restricted SOP |
| 2 | **3,380** `reasoning`, 272 `delta`, `citations`, `ANSWERED` | 716 `reasoning`, `ANSWERED` | same |
| 3 | 2,291 `reasoning`, 233 `delta`, `citations`, `ANSWERED` | 885 `reasoning`, `ANSWERED` | same |

No `finalText` contained reasoning. `docker logs` of the container: `llm_output_truncated` 0, `answer_empty` 0, `Traceback` 0. Run 2's reasoning alone (3,380 events against 1,366 for the cut-off run) would not have fit the old 3,000-token ceiling. The guard path itself (`ERROR` / `LLM_UNAVAILABLE`) was not triggered live; it is covered by the unit tests.

**Guard path live and in the browser (2026-11-17).** The parity `ai-service` was started once with `SOPILOT_LLM_MAX_OUTPUT_TOKENS=64` (a scratch override file, not in the repo) so the reasoning always runs out; headless Chromium (Playwright 1.58 from the owner's local Excalidraw clone, no repo dependency) against the throwaway parity web `:13000`, dev sign-in, screenshots in `artifacts/testing/v2-43-live-2026-11-17/browser/` (gitignored). Owner asks "Buddy program là gì?": the answer block shows "Thought for 2 s", then the fixed `LLM_UNAVAILABLE` text in the question's language ("Dịch vụ trả lời đang không khả dụng. Vui lòng thử lại sau ít phút.") and "Try again"; no empty answer, no citations. Log: `llm_output_truncated max_tokens=64`, then `answer_empty reasoning_chars=238`. The service was restarted without the override afterwards (variable unset, `models.yaml` default 8192).

**Docker suites (2026-11-17, merged tree).** ai-service `run-tests -Type integration`: "151 passed". CI on PR #19 (`ci.yml` + `tenant-isolation.yml`): all 13 checks pass.

**Not verified.** An integration test through `QAService.ask` for the empty-answer path (the review's suggestion; the path was exercised live instead).
