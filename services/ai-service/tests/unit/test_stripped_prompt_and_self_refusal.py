"""A stripped question reaches the model stripped, and a self-refusal is only the fixed sentence.

No network, no model: the steps run on a hand-built ``QAContext``; the outcome is read through
``QAService._outcome``.
"""
from __future__ import annotations

from datetime import date

from sopilot_ai.conversations.service import QAService
from sopilot_ai.conversations.steps import BuildPromptStep, QAContext, SelfRefusalStep
from sopilot_ai.qa.pipeline import DecisionKind
from sopilot_ai.qa.templates import render

RUDE = "địt mẹ mày cho tao hỏi quy trình nghỉ phép"
CLEAN = "cho tao hỏi quy trình nghỉ phép"


def _prompt_user_text(ctx: QAContext) -> str:
    assert ctx.prompt is not None
    return ctx.prompt.messages[1]["content"]


async def test_the_prompt_asks_the_stripped_question_not_the_original() -> None:
    ctx = QAContext(question=RUDE, lang="vi", today=date(2026, 11, 18))
    ctx.text, ctx.working_text = RUDE, CLEAN
    await BuildPromptStep().run(ctx)
    user = _prompt_user_text(ctx)
    assert CLEAN in user and "địt" not in user


async def test_the_prompt_falls_back_to_the_original_when_nothing_was_stripped() -> None:
    ctx = QAContext(question="quy trình nghỉ phép", lang="vi", today=date(2026, 11, 18))
    ctx.text = ctx.working_text = "quy trình nghỉ phép"
    await BuildPromptStep().run(ctx)
    assert "quy trình nghỉ phép" in _prompt_user_text(ctx)


async def test_a_rewritten_question_keeps_the_stripped_one_as_the_original() -> None:
    ctx = QAContext(question=RUDE, lang="vi", today=date(2026, 11, 18))
    ctx.text, ctx.working_text, ctx.rewritten = RUDE, CLEAN, "Quy trình nghỉ phép năm là gì?"
    await BuildPromptStep().run(ctx)
    user = _prompt_user_text(ctx)
    assert "Quy trình nghỉ phép năm là gì?" in user and f"Câu gốc: {CLEAN}" in user
    assert "địt" not in user


async def test_an_answer_that_opens_with_not_found_ends_as_the_fixed_sentence_only() -> None:
    opening = render("not_found_opening", "vi")
    ctx = QAContext(question=RUDE, lang="vi")
    ctx.final_text = ctx.answer_text = (
        f"{opening}\n\n(Lưu ý: theo quy tắc số 4 …)\n\n1. Đối tượng áp dụng [5].")
    ctx.citations = ["stale"]  # type: ignore[list-item]
    decision = await SelfRefusalStep().run(ctx)
    assert decision.kind is DecisionKind.REFUSE and ctx.checks["citationCount"] == 0
    outcome, reason, text, closing = QAService._outcome(None, ctx, decision)  # type: ignore[arg-type]
    assert outcome == "REFUSED_NO_EVIDENCE" and reason == "GENERATOR_NOT_FOUND"
    assert text == opening
    assert [(e.name, e.data) for e in closing] == [
        ("refusal", {"text": opening, "reason": "GENERATOR_NOT_FOUND"})]


async def test_the_not_found_sentence_follows_the_question_language() -> None:
    ctx = QAContext(question="How many leave days?", lang="en")
    ctx.final_text = ctx.answer_text = render("not_found_opening", "en") + " Extra text."
    decision = await SelfRefusalStep().run(ctx)
    *_, text, _closing = QAService._outcome(None, ctx, decision)  # type: ignore[arg-type]
    assert text == render("not_found_opening", "en")


async def test_a_normal_answer_is_not_touched_by_the_self_refusal_step() -> None:
    ctx = QAContext(question="How many leave days?", lang="en")
    ctx.final_text = ctx.answer_text = "Twelve days [1]."
    decision = await SelfRefusalStep().run(ctx)
    assert decision.kind is DecisionKind.CONTINUE
