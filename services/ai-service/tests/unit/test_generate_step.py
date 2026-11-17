"""V2-43: a generation that ends with no answer text is an error, never an empty ``ANSWERED``.

No network: the chain is the scripted fake; the outcome is read through ``QAService._outcome``.
"""
from __future__ import annotations

from datetime import date

from fakes import ScriptedChain
from sopilot_ai.conversations.service import QAService
from sopilot_ai.conversations.steps import GenerateStep, QAContext
from sopilot_ai.providers.llm import Thought
from sopilot_ai.qa.pipeline import DecisionKind
from sopilot_ai.qa.prompt import build_prompt


async def _generate(pieces):  # noqa: ANN001, ANN202
    events: list[tuple[str, object]] = []
    ctx = QAContext(question="How many leave days?", lang="en",
                    emit=lambda name, data: events.append((name, data)))
    ctx.prompt = build_prompt(question=ctx.question, sources=[], lang="en",
                              today=date(2026, 11, 17))
    decision = await GenerateStep(ScriptedChain(pieces)).run(ctx)
    outcome = QAService._outcome(None, ctx, decision)  # type: ignore[arg-type]
    return decision, ctx, events, outcome


async def test_a_stream_of_only_reasoning_ends_as_an_error_not_answered() -> None:
    # The UC-04 failure: the output ceiling ran out mid-reasoning, so no answer text arrived.
    decision, ctx, events, (outcome, reason, text, closing) = await _generate(
        [Thought("Check the leave table. "), Thought("Twelve days under five ye")])
    assert decision.kind is DecisionKind.REFUSE and outcome == "ERROR"
    assert ctx.error_code == "LLM_UNAVAILABLE" and ctx.checks["emptyAnswer"] is True
    assert reason is None and text == "The answering service is not available. " \
                                      "Please try again in a few minutes."
    assert closing == []  # no citations event, no delta
    names = [n for n, _ in events]
    assert "reasoning_done" in names and "delta" not in names and "citations" not in names


async def test_a_stream_with_no_deltas_at_all_ends_as_an_error() -> None:
    _, ctx, events, (outcome, *_rest) = await _generate([])
    assert outcome == "ERROR" and ctx.error_code == "LLM_UNAVAILABLE" and events == []


async def test_a_whitespace_only_answer_after_reasoning_is_not_an_answer() -> None:
    _, ctx, _, (outcome, *_rest) = await _generate([Thought("weigh it"), "  \n "])
    assert outcome == "ERROR" and ctx.checks["emptyAnswer"] is True


async def test_reasoning_followed_by_answer_text_is_still_answered() -> None:
    decision, ctx, events, (outcome, reason, _text, _closing) = await _generate(
        [Thought("weigh the sources"), "Twelve days."])
    assert decision.kind is DecisionKind.CONTINUE and ctx.answer_text == "Twelve days."
    assert outcome == "ANSWERED" and reason is None and ctx.error_code is None
    assert "emptyAnswer" not in ctx.checks
    assert "".join(d["text"] for n, d in events if n == "delta") == "Twelve days."  # type: ignore[index]
