"""The deterministic steps of the QA pipeline: input, PII, frame, guard, router, meaningful tokens.

No LLM and no storage here. The only outside call is the injected ``known_terms`` lookup of the
meaningful-token check. Retrieval, prompt and generation steps are added with the API.
"""
from __future__ import annotations

from sopilot_ai.qa import guard as guard_mod
from sopilot_ai.qa import pii, router
from sopilot_ai.qa.pipeline import (
    CONTINUE,
    Decision,
    PipelineContext,
    Step,
    refuse,
    template,
)
from sopilot_ai.qa.query_frame import QueryFrame, build_query_frame
from sopilot_ai.qa.textnorm import nfc, tokenize_words


class InputStep:
    """Empty or over-long questions are refused, never truncated (D4)."""

    name = "input"

    async def run(self, ctx: PipelineContext) -> Decision:
        ctx.text = nfc(ctx.question)
        if not ctx.text.strip():
            return template("input_empty", reason="INPUT_INVALID", rule_id="input.empty")
        if len(ctx.text) > ctx.max_question_chars:
            return template("input_too_long", reason="INPUT_INVALID", rule_id="input.too_long",
                            max_chars=ctx.max_question_chars)
        return CONTINUE


class PiiStep:
    """Mask PII before anything else looks at the text (D8)."""

    name = "pii"

    async def run(self, ctx: PipelineContext) -> Decision:
        result = pii.mask_pii(ctx.text)
        ctx.text = result.text
        for rule_id in result.rule_ids:
            ctx.record("INPUT_FLAG", rule_id)
        if result.rule_ids:
            ctx.checks["pii"] = list(result.rule_ids)
        return CONTINUE


class FrameStep:
    """Build the :class:`QueryFrame` once; later steps read it."""

    name = "frame"

    async def run(self, ctx: PipelineContext) -> Decision:
        known: set[str] = set()
        if ctx.known_terms is not None:
            words = sorted({t.raw for t in tokenize_words(ctx.text)})
            known = await ctx.known_terms(words)
        ctx.frame = build_query_frame(ctx.text, lang=ctx.lang_override, known_terms=known,
                                      followup_max_tokens=ctx.followup_max_tokens)
        ctx.route_info["signals"] = ctx.frame.signals()
        ctx.route_info["lang"] = ctx.frame.lang
        return CONTINUE


class GuardStep:
    """Block injection and real-harm requests; flag the mild ones; remember profanity."""

    name = "guard"

    async def run(self, ctx: PipelineContext) -> Decision:
        frame = _frame(ctx)
        ctx.guard = guard_mod.inspect(frame.text, frame.tokens)
        for rule_id in ctx.guard.flag_rules:
            ctx.record("INPUT_FLAG", rule_id)
        for rule_id in ctx.guard.abuse_rules:
            ctx.record("INPUT_FLAG", rule_id)
        if ctx.guard.blocked:
            ctx.record("INPUT_BLOCK", ctx.guard.blocked_rule or "")
            key = ctx.guard.block_template
            if key == "self_harm" and not ctx.support_contact.strip():
                key = "self_harm_no_contact"  # never print "contact ." with an empty contact
            return refuse("REFUSED_GUARD", template_key=key, rule_id=ctx.guard.blocked_rule,
                          support_contact=ctx.support_contact)
        return CONTINUE


class RouterStep:
    """Strip greetings, thanks and profanity; a question with nothing left gets a sentence."""

    name = "router"

    async def run(self, ctx: PipelineContext) -> Decision:
        frame = _frame(ctx)
        abuse = ctx.guard.abuse_indexes if ctx.guard else ()
        ctx.stripped = router.strip_words(frame, abuse)
        ctx.working_text = ctx.stripped.working_text
        ctx.route_info["layer"] = "rule"
        ctx.route_info["stripped"] = list(ctx.stripped.kinds)
        return _route_decision(ctx, router.judge(frame, ctx.stripped, check_meaningful=False))


class MeaningfulTokensStep:
    """Too few meaningful tokens left after stripping: "not understood", no retrieval (D4)."""

    name = "meaningful_tokens"

    def __init__(self, min_meaningful: int | None = None) -> None:
        self.min_meaningful = min_meaningful

    async def run(self, ctx: PipelineContext) -> Decision:
        frame = _frame(ctx)
        if ctx.stripped is None:
            raise RuntimeError("the router step must run first")
        result = router.judge(frame, ctx.stripped, min_meaningful=self.min_meaningful)
        ctx.route_info["meaningful"] = frame.meaningful_count(ctx.stripped.removed)
        return _route_decision(ctx, result)


def _route_decision(ctx: PipelineContext, result: router.RouteResult) -> Decision:
    ctx.route = result
    if not result.answered_by_template:
        return CONTINUE
    ctx.route_info["intent"] = result.template_key
    return template(result.template_key or router.KIND_NOT_UNDERSTOOD, reason=result.refusal_reason,
                    rule_id=f"template.{result.template_key}")


def _frame(ctx: PipelineContext) -> QueryFrame:
    if ctx.frame is None:
        raise RuntimeError("the frame step must run first")
    return ctx.frame


def deterministic_steps() -> list[Step]:
    """Steps 2-7 of TECH-V2-ai-service §7.1 in order; quota and later steps come with the API."""
    return [InputStep(), PiiStep(), FrameStep(), GuardStep(), RouterStep(),
            MeaningfulTokensStep()]
