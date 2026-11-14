"""Answering one question: the pipeline, the SSE events and what is stored (TECH §7.1, §7.2).

``QAService.answer`` is an async generator of :class:`Event`. The steps run in a task and put
events on a queue while they work, so ``delta`` events leave as the model writes. When the chain
ends, the turn is stored in one transaction and only then do the closing events (``citations``,
``done``) go out, so a client that saw ``done`` can always read the message back.

The tenant comes from the verified principal only. Every statement runs in ``tenant_tx`` and
carries ``workspace_id`` and ``user_id``; there is no code path that reads another user's turn.
"""
from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.conversations import repository as repo
from sopilot_ai.conversations.events import Event
from sopilot_ai.conversations.steps import (
    BuildContextStep,
    BuildPromptStep,
    ChatChain,
    CitationStep,
    GenerateStep,
    NumberCheckStep,
    QAContext,
    QuotaStep,
    RetrieveStep,
    RewriteStep,
    SelfRefusalStep,
    SemanticRouterStep,
)
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.qa import pii, templates
from sopilot_ai.qa.pipeline import (
    Decision,
    DecisionKind,
    Step,
    refuse,
    run_steps,
)
from sopilot_ai.qa.prompt import PROMPT_VERSION
from sopilot_ai.qa.query_frame import detect_lang
from sopilot_ai.qa.router import SemanticLayer
from sopilot_ai.qa.steps import deterministic_steps
from sopilot_ai.qa.textnorm import nfc
from sopilot_ai.quota.counters import FREE_OUTCOMES, QuotaCounter
from sopilot_ai.retrieval import search
from sopilot_ai.retrieval.access_filter import Principal
from sopilot_ai.retrieval.context import ContextConfig, context_sources_json
from sopilot_ai.retrieval.retriever import Retriever

log = structlog.get_logger(__name__)

TITLE_MAX_CHARS = 60
HISTORY_TURNS = 3
_SPACES = re.compile(r"\s+")
_ERROR_TEMPLATES = {"QUOTA_EXCEEDED": "error_quota_exceeded",
                    "LLM_UNAVAILABLE": "error_llm_unavailable",
                    "INTERNAL_ERROR": "error_internal"}


class ConversationNotFound(Exception):
    """Not the caller's, deleted, or never existed: the three look the same (FR-19)."""


@dataclass(frozen=True)
class ConversationRef:
    id: UUID
    new: bool  # created with the first message, so nothing is stored if the request never ends


def make_title(question: str, limit: int = TITLE_MAX_CHARS) -> str:
    """Title from the PII-masked question by rule: first words, cut at a word boundary (no LLM)."""
    text = _SPACES.sub(" ", pii.mask_pii(nfc(question)).text).strip()
    if not text:
        return "Cuộc hội thoại mới"
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return cut.rstrip(" ,.;:-") + "…"


class QAService:
    def __init__(self, engine: AsyncEngine, retriever: Retriever, generate: ChatChain,
                 rewrite: ChatChain, *, context: ContextConfig, quota: QuotaCounter,
                 max_question_chars: int = 1000, followup_max_tokens: int | None = None,
                 support_contact: str = "", timezone: str = "Asia/Ho_Chi_Minh",
                 now: Callable[[], datetime] | None = None,
                 semantic: SemanticLayer | None = None) -> None:
        self.engine = engine
        self.retriever = retriever
        self.generate = generate
        self.rewrite = rewrite
        self.context = context
        self.quota = quota
        self.max_question_chars = max_question_chars
        self.followup_max_tokens = followup_max_tokens
        self.support_contact = support_contact
        self.semantic = semantic  # V2-27 router; None = the V2-10 rule router only
        tz = ZoneInfo(timezone)
        self._now = now or (lambda: datetime.now(tz))
        self._detached: set[asyncio.Task[None]] = set()

    # -- conversations ---------------------------------------------------------------------

    async def open(self, principal: Principal, conversation_id: UUID | None) -> ConversationRef:
        """``None`` starts a new conversation; an id must be the caller's own."""
        if conversation_id is None:
            return ConversationRef(uuid4(), True)
        async with tenant_tx(self.engine, principal.workspace_id, principal.user_id) as conn:
            row = await repo.get_conversation(conn, principal, conversation_id)
        if row is None:
            raise ConversationNotFound
        return ConversationRef(conversation_id, False)

    def steps(self) -> list[Step]:
        """The chain in the order of TECH §7.1 (``qa.pipeline.STEP_ORDER``)."""
        router = [SemanticRouterStep(self.semantic, self.engine)] if self.semantic else []
        return [QuotaStep(self.quota), *deterministic_steps(), *router, RewriteStep(self.rewrite),
                RetrieveStep(self.retriever, self.engine),
                BuildContextStep(self.engine, self.context, self.generate), BuildPromptStep(),
                GenerateStep(self.generate), CitationStep(), SelfRefusalStep(),
                NumberCheckStep()]

    # -- one question ----------------------------------------------------------------------

    async def answer(self, principal: Principal, ref: ConversationRef, content: str,
                     lang: str | None = None) -> AsyncIterator[Event]:
        started = time.monotonic()
        user_created = self._now()
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        ctx = QAContext(
            question=content, lang_override=lang, max_question_chars=self.max_question_chars,
            followup_max_tokens=self.followup_max_tokens, support_contact=self.support_contact,
            principal=principal, lang=detect_lang(content, lang), today=user_created.date(),
            conversation_id=None if ref.new else ref.id,
            emit=lambda name, data: queue.put_nowait(Event(name, data)))

        async def known_terms(words: Sequence[str]) -> set[str]:
            async with tenant_tx(self.engine, principal.workspace_id, principal.user_id) as conn:
                return await search.known_terms(conn, principal, words)

        ctx.known_terms = known_terms
        user_id, assistant_id = uuid4(), uuid4()
        yield Event("meta", {"conversationId": str(ref.id), "messageId": str(assistant_id),
                             "mode": self.retriever.mode, "lang": ctx.lang})
        task = asyncio.create_task(self._run(ctx, ref, queue))
        try:
            while (item := await queue.get()) is not None:
                yield item
            decision = await task
        except (asyncio.CancelledError, GeneratorExit):
            task.cancel()
            # The client left: keep a record and give the question back, outside this task's
            # cancellation (a plain await here would be cancelled again).
            self._detach(self._store_aborted(principal, ref, ctx, content, user_id, assistant_id,
                                             user_created, started))
            raise

        outcome, reason, text, closing = self._outcome(ctx, decision)
        if ctx.reservation is not None and outcome in FREE_OUTCOMES:
            ctx.reservation = await self._release(principal, ctx)
        rec = self._record(principal, ref, ctx, content, user_id, assistant_id, user_created,
                           started, outcome, reason, text)
        try:
            async with tenant_tx(self.engine, principal.workspace_id, principal.user_id) as conn:
                await repo.save_turn(conn, principal, rec)
        except Exception as exc:  # noqa: BLE001 - a storage failure must not leak its message
            log.error("qa_store_failed", error=type(exc).__name__)
            if ctx.reservation is not None:  # an error is free: the question was not answered
                ctx.reservation = await self._release(principal, ctx)
            yield self._error("INTERNAL_ERROR", ctx.lang)
            return
        if outcome in ("ERROR", "QUOTA_EXCEEDED"):
            yield self._error(ctx.error_code or "INTERNAL_ERROR", ctx.lang)
            return
        for event in closing:
            yield event
        left = ctx.reservation.questions_left if ctx.reservation is not None else None
        yield Event("done", {
            "finalText": text, "outcome": outcome, "refusalReason": reason,
            "warnings": ctx.warnings,
            "usage": None if left is None else {"questionsLeftToday": left}})

    # -- internals -------------------------------------------------------------------------

    async def _run(self, ctx: QAContext, ref: ConversationRef,
                   queue: asyncio.Queue[Event | None]) -> Decision:
        try:
            assert ctx.principal is not None
            if not ref.new:
                async with tenant_tx(self.engine, ctx.principal.workspace_id,
                                     ctx.principal.user_id) as conn:
                    pairs = await repo.recent_turns(conn, ctx.principal, ref.id, HISTORY_TURNS)
                ctx.history = [(pii.mask_pii(q).text, pii.mask_pii(a).text) for q, a in pairs]
            return await run_steps(self.steps(), ctx)
        except Exception as exc:  # noqa: BLE001 - the client gets a fixed code, not the message
            log.error("qa_pipeline_failed", error=type(exc).__name__,
                      last_step=(ctx.route_info.get("steps") or [None])[-1])
            ctx.error_code = "INTERNAL_ERROR"
            return refuse("ERROR", rule_id="internal")
        finally:
            queue.put_nowait(None)

    def _outcome(self, ctx: QAContext, d: Decision) -> tuple[str, str | None, str, list[Event]]:
        """``(outcome, refusal_reason, text, closing events)`` of a finished chain."""
        lang = ctx.lang
        if d.kind is DecisionKind.CONTINUE:
            closing = [Event("citations", [self._citation(ctx, c) for c in ctx.citations])] \
                if ctx.citations else []
            text = ctx.final_text
            # V2-27 (b): a fixed disclaimer after the answer and before `citations`, stored too.
            for intent in ctx.checks.get("disclaimers", []):
                note = "\n\n" + templates.render(f"disclaimer_{intent}", lang)
                text += note
                closing.insert(0, Event("delta", {"text": note}))
            return "ANSWERED", None, text, closing
        outcome = d.outcome or "TEMPLATE"
        if outcome in ("ERROR", "QUOTA_EXCEEDED"):
            code = ctx.error_code or "INTERNAL_ERROR"
            return outcome, None, ctx.answer_text or templates.render(_ERROR_TEMPLATES[code],
                                                                      lang), []
        if d.template_key is None:  # the model refused in its own words (GENERATOR_NOT_FOUND)
            return outcome, d.refusal_reason, ctx.final_text, []
        text = templates.render(d.template_key, lang, **d.template_values)
        reason = d.refusal_reason
        if d.kind is DecisionKind.TEMPLATE and reason is None:
            # A greeting or a thanks is an answer, not a refusal: plain text.
            return outcome, None, text, [Event("delta", {"text": text})]
        if outcome == "REFUSED_GUARD" and ctx.replaced:
            return outcome, None, text, []  # the `replace` event already carried the sentence
        payload: dict = {"text": text, "reason": "GUARD" if outcome == "REFUSED_GUARD" else reason}
        if reason == "NO_EVIDENCE":
            payload["nearestDocuments"] = ctx.nearest
        return outcome, reason, text, [Event("refusal", payload)]

    @staticmethod
    def _citation(ctx: QAContext, c) -> dict:  # noqa: ANN001
        return {"n": c.n, "documentId": str(c.document_id), "versionId": str(c.version_id),
                "title": ctx.titles.get(c.version_id), "page": c.page_start,
                "charStart": c.char_start, "charEnd": c.char_end, "snippet": c.snippet}

    def _record(self, principal: Principal, ref: ConversationRef, ctx: QAContext, content: str,
                user_id: UUID, assistant_id: UUID, user_created: datetime, started: float,
                outcome: str, reason: str | None, text: str) -> repo.TurnRecord:
        ctx.timings["total"] = round((time.monotonic() - started) * 1000)
        route = {**ctx.route_info, "llmCalls": ctx.llm_calls}
        result = ctx.retrieval
        end = self._now()
        if end <= user_created:  # the two rows must sort question first
            end = user_created + timedelta(milliseconds=1)
        return repo.TurnRecord(
            conversation_id=ref.id, new_conversation=ref.new, title=make_title(content),
            user_message_id=user_id, assistant_message_id=assistant_id, question=content,
            lang=ctx.lang, answer=text, outcome=outcome, refusal_reason=reason,
            user_created=user_created, assistant_created=end, standalone_query=ctx.rewritten,
            rewrite_status=ctx.rewrite_status, route=route, checks=ctx.checks,
            retrieval_mode=result.mode if result else None,
            gate_score=result.gate_score if result else None,
            threshold=result.threshold if result else None, model=ctx.model,
            prompt_version=PROMPT_VERSION if ctx.prompt else None, latency_ms=ctx.timings,
            context_sources=context_sources_json(ctx.sources) if ctx.sources else None,
            citations=ctx.citations, guard_events=ctx.guard_events, retrieval=result)

    async def _release(self, principal: Principal, ctx: QAContext):  # noqa: ANN202
        assert ctx.reservation is not None
        try:
            return await self.quota.release(principal.workspace_id, principal.user_id,
                                            ctx.reservation)
        except Exception as exc:  # noqa: BLE001
            log.error("quota_release_failed", error=type(exc).__name__)
            return ctx.reservation

    async def _store_aborted(self, principal: Principal, ref: ConversationRef, ctx: QAContext,
                             content: str, user_id: UUID, assistant_id: UUID,
                             user_created: datetime, started: float) -> None:
        ctx.error_code = "INTERNAL_ERROR"
        ctx.route_info["aborted"] = True
        if ctx.reservation is not None:
            ctx.reservation = await self._release(principal, ctx)
        rec = self._record(principal, ref, ctx, content, user_id, assistant_id, user_created,
                           started, "ERROR", None, ctx.answer_text)
        try:
            async with tenant_tx(self.engine, principal.workspace_id, principal.user_id) as conn:
                await repo.save_turn(conn, principal, rec)
        except Exception as exc:  # noqa: BLE001
            log.error("qa_store_aborted_failed", error=type(exc).__name__)

    def _detach(self, coro) -> None:  # noqa: ANN001
        task = asyncio.ensure_future(coro)
        self._detached.add(task)
        task.add_done_callback(self._detached.discard)

    @staticmethod
    def _error(code: str, lang: str) -> Event:
        return Event("error", {"code": code,
                               "message": templates.render(_ERROR_TEMPLATES[code], lang)})
