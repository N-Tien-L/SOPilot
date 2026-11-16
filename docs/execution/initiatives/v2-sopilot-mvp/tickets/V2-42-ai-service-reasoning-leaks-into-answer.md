---
id: V2-42
title: "ai-service: the model's reasoning is streamed as answer text"
type: fix
status: review
created: 2026-11-16
updated: 2026-11-17
author: "Owner"
scope: ai-qa
priority: P0
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-32]
blocks: [V2-17]
branch: "fix/ai-reasoning-pump"
assignee: pair
refs:
  - docs/architecture/components/ai-service.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-17-parity-and-legacy-removal.md
---

# TICKET V2-42: Reasoning streamed as answer text

> **Scope:** `ai-qa` | **Size:** `S` | **Priority:** `P0`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `fix/ai-reasoning-pump`

## 1. Context & goal
Found by the V2-17 parity run (2026-11-16, throwaway stack, Modal answer model with thinking on): every answer's `delta` events and `done.finalText` started with the model's reasoning ("Thinking Process: 1. **Analyze the Request:** … Rules: 1. Use only information from `<source>` tags…"), then "Ready to output.cw", then the real cited answer. No `reasoning` events were sent. UC-04 and FR-11 were recorded `not passed` in the V2-17 parity record (`TEST-REPORT-001`, `docs/quality/test-reports/parity-v2-17-2026-11-16.md` on `chore/infra-remove-legacy`, Finding F1) and V2-17 stopped.

**Cause (confirmed).** The provider splits the stream correctly: the raw Modal stream holds `…cw\n</think>\n\n<answer>`, `generate.thinking` is `True`, and `ThinkSplitter` (`providers/llm.py`) yields the reasoning as `Thought` (a `str` subclass). `_pump` (`conversations/steps.py`, V2-10) handed every delta on as `str(value)`, which turns a `Thought` into a plain `str`. `GenerateStep` (V2-32) tells reasoning from answer by `isinstance(delta, Thought)`, so that check was never true and all reasoning went down the answer path. V2-32's tests covered the splitter and `_ThoughtStream` separately; none ran a `Thought` through `_pump` and `GenerateStep`.

Goal: reasoning reaches the client only as `reasoning` / `reasoning_done` events (the existing "Thought for N s" block, owner decision 2026-11-16) and never as answer text or stored message content.

## 2. Acceptance criteria
- [x] **Failing test first.** `test_pump_keeps_reasoning_marked_as_reasoning` (unit) and `test_the_models_reasoning_goes_out_as_reasoning_never_as_answer_text` (integration, scripted model streaming `Thought` pieces then text) fail on the unchanged code for the reported reason.
- [x] **Fix.** `_pump` yields each delta unchanged; both tests pass.
- [x] **No regression.** The ai-service suite and ruff pass.
- [x] **Live.** On the throwaway parity stack with this branch's ai-service, answerable questions send `reasoning` events and a clean `finalText` with citations.
- [ ] Owner review; then V2-17 re-runs UC-04 and FR-11 on `develop` after the merge.

## 3. Guide
- Code: `services/ai-service/src/sopilot_ai/conversations/steps.py` (`_pump`, `GenerateStep`), `providers/llm.py` (`Thought`, `ThinkSplitter`).
- Not in this ticket: the output guard's handling of paraphrased rules inside the reasoning (owner decision 2026-11-16: the reasoning block stays visible; only the canary and 40-character verbatim echoes withhold it), the model's stray "cw" before `</think>` (it now stays inside the reasoning).

## 4. Testing
```powershell
cd services/ai-service
uv run --extra dev pytest tests/unit/test_qa_api_units.py::test_pump_keeps_reasoning_marked_as_reasoning tests/integration/test_qa_api.py::test_the_models_reasoning_goes_out_as_reasoning_never_as_answer_text -q
uv run --extra dev ruff check
uv run --extra dev --extra pdf pytest tests/ -q   # Docker for tests/integration
```

## 5. Changed files
| Area | Action |
|---|---|
| `services/ai-service/src/sopilot_ai/conversations/steps.py` | MODIFY (`_pump` yields the delta unchanged) |
| `services/ai-service/tests/unit/test_qa_api_units.py`, `tests/integration/test_qa_api.py` | MODIFY (two regression tests) |
| PLAN (`total_tickets`, DAG, tables, change log), `depends_on`/`blocks` of V2-10, V2-17, V2-32 | MODIFY |
| `eval/tests/test_review_regressions.py` (pinned ticket count 41 → 42) | MODIFY |

## 6. Results
Implemented on `fix/ai-reasoning-pump` (from `develop` 345f1c8), committed 2026-11-17 and merged into `develop` locally on the owner's request; not pushed. Status `review`: owner acceptance moves it to `done`.

**Reproduction first.** Both new tests failed on the unchanged code: `assert [False, False] == [True, False]` (`test_qa_api_units.py`) and `assert '' == 'Rules: use o...ays two days.'` (`test_qa_api.py`): no `reasoning` event, the reasoning was in the answer.

**Change.** `steps.py:136` `yield str(value)` → `yield value`.

**Evidence.**
- The two new tests: "2 passed".
- `uv run --extra dev ruff check`: "All checks passed!".
- `uv run --extra dev --extra pdf pytest tests/ -q`: "767 passed, 1 skipped, 15 xfailed". The skip is `test_guard_cases.py:172` ("eval/datasets is git-ignored"), absent in a fresh worktree.
- Live (2026-11-16, throwaway `sopilot-parity` stack, ai-service built from this branch, Modal answer model, rerank on): owner question "Buddy program là gì?" → 1500 `reasoning` events, `reasoning_done`, 299 `delta`, `citations`, `finalText` starts "Theo tài liệu, \"GitLab Buddy Program\" là…" with `[1]`; engineer question on the department-restricted SOP → 1106 `reasoning` events, `finalText` "Báo cáo tai nạn lao động phải được gửi cho trưởng bộ phận trong vòng 24 giờ kể từ khi xảy ra tai nạn [1]." citing that SOP; HR member and an uncovered question → `REFUSED_NO_EVIDENCE`. No `finalText` contained "Thinking Process", "Analyze the Request" or `<source>`.

**Not verified.** A browser view of the reasoning block with this fix; a `v2-reviewer` pass (skipped: one-line code change plus tests). In this worktree `eval` shows 23 failures that need the gitignored `eval/datasets` and `datasets/extraction`; a clean `develop` worktree shows the same 23, and in the main tree those files pass (50 passed).
