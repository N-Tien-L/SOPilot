"""The steps of the QA pipeline that need storage, retrieval or the LLM (TECH-V2-ai-service §7.1).

The deterministic steps (input, PII, frame, guard, router, meaningful tokens) are in
``qa/steps.py`` and do no I/O. These come before and after them: quota, rewrite, retrieval and
gate, context, prompt, generation with the output guard, citations, self-refusal, number check.

Each step reads and writes one :class:`QAContext` and returns a ``Decision``. A step that streams
puts events on ``ctx.emit``; the service forwards them while the chain is still running.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.providers.llm import LLMError, estimate_tokens
from sopilot_ai.qa import checks as qa_checks
from sopilot_ai.qa import citations as qa_citations
from sopilot_ai.qa import prompt as qa_prompt
from sopilot_ai.qa.output_guard import OutputGuard, Verdict
from sopilot_ai.qa.pipeline import (
    CONTINUE,
    Decision,
    PipelineContext,
    refuse,
    template,
)
from sopilot_ai.quota.counters import QuotaCounter, Reservation
from sopilot_ai.retrieval import context_store, search
from sopilot_ai.retrieval.access_filter import Principal
from sopilot_ai.retrieval.context import ContextConfig, Source, build_sources, group_keys
from sopilot_ai.retrieval.retriever import RetrievalResult, Retriever

NEAREST_DOCUMENTS = 3


class ChatChain(Protocol):
    """What the steps need from ``providers.llm.LLMChain`` (tests pass a scripted one)."""

    @property
    def context_budget(self) -> int | None: ...

    def stream(self, messages: Sequence[dict[str, str]], *, tokens: int,
               on_start: Callable[[str], None] | None = None) -> Iterator[str]: ...

    def complete(self, messages: Sequence[dict[str, str]], *, tokens: int,
                 temperature: float | None = None,
                 on_start: Callable[[str], None] | None = None) -> str: ...


@dataclass
class QAContext(PipelineContext):
    """One question's state, extended with what the I/O steps produce."""

    principal: Principal | None = None
    lang: str = "vi"  # resolved once, from the request or the text; templates and prompt use it
    today: date | None = None
    history: list[tuple[str, str]] = field(default_factory=list)  # masked (question, answer)
    emit: Callable[[str, Any], None] = field(default=lambda name, data: None, repr=False)

    reservation: Reservation | None = None
    rewritten: str | None = None
    rewrite_status: str = "NONE"
    retrieval: RetrievalResult | None = None
    nearest: list[dict[str, str]] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    source_texts: list[qa_prompt.SourceText] = field(default_factory=list)
    titles: dict[UUID, str | None] = field(default_factory=dict)  # version_id -> title
    prompt: qa_prompt.PromptBundle | None = None

    answer_text: str = ""  # what the model produced
    final_text: str = ""  # after the citation clean-up
    citations: list[qa_citations.Citation] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    model: str | None = None
    replaced: bool = False  # a `replace` event already told the client the text is withdrawn
    error_code: str | None = None  # QUOTA_EXCEEDED | LLM_UNAVAILABLE | INTERNAL_ERROR

    llm_calls: int = 0
    timings: dict[str, int] = field(default_factory=dict)

    @property
    def query(self) -> str:
        """What retrieval searches for: the rewritten question, else the stripped one."""
        return self.rewritten or self.working_text or self.text


async def _pump(gen: Iterator[str], stop: threading.Event) -> AsyncIterator[str]:
    """Deltas of a blocking generator, read on one worker thread.

    The generator is only ever touched by that thread: it reads, and it closes the stream (so the
    HTTP connection is released) when it ends, fails or sees ``stop``. A cancelled caller sets
    ``stop`` and returns at once; closing from another thread would race the read in progress.
    A read that is blocked on the network ends when the next delta or the HTTP timeout arrives.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    def put(item: tuple[str, Any]) -> None:
        with contextlib.suppress(RuntimeError):  # the loop is gone: nobody is listening
            loop.call_soon_threadsafe(queue.put_nowait, item)

    def work() -> None:
        try:
            for delta in gen:
                if stop.is_set():
                    break
                put(("delta", delta))
            put(("end", None))
        except BaseException as exc:  # noqa: BLE001 - handed to the consumer, never lost
            put(("error", exc))
        finally:
            close = getattr(gen, "close", None)
            if close is not None:
                close()

    loop.run_in_executor(None, work)
    while True:
        kind, value = await queue.get()
        if kind == "delta":
            yield str(value)
        elif kind == "error":
            raise value
        else:
            return


def _ms(start: float) -> int:
    return round((time.monotonic() - start) * 1000)


class QuotaStep:
    """Step 1: reserve a question when a limit is on; ``QUOTA_EXCEEDED`` when it is full."""

    name = "quota"

    def __init__(self, counter: QuotaCounter) -> None:
        self.counter = counter

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        if not self.counter.enabled:
            return CONTINUE
        assert c.principal is not None and c.today is not None
        c.reservation = await self.counter.reserve(c.principal.workspace_id, c.principal.user_id,
                                                   c.today)
        if c.reservation.allowed:
            return CONTINUE
        c.error_code = "QUOTA_EXCEEDED"
        return refuse("QUOTA_EXCEEDED", rule_id=f"quota.{c.reservation.state.value}")


class RewriteStep:
    """Step 7: a standalone question from the last turns, only when there is history (D5)."""

    name = "rewrite"

    def __init__(self, chain: ChatChain) -> None:
        self.chain = chain

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        if not c.history:
            c.rewrite_status = "NONE"
            return CONTINUE
        messages = qa_prompt.build_rewrite_prompt(c.history, c.working_text or c.text)
        tokens = estimate_tokens(" ".join(m["content"] for m in messages))
        rewritten: str | None = None
        start = time.monotonic()
        c.llm_calls += 1
        try:
            raw = await asyncio.to_thread(self.chain.complete, messages, tokens=tokens,
                                          temperature=0.0)
            rewritten = qa_prompt.clean_rewrite(raw, max_chars=c.max_question_chars)
        except LLMError:
            rewritten = None
        c.timings["rewrite"] = _ms(start)
        if rewritten:
            c.rewritten, c.rewrite_status = rewritten, "OK"
            return CONTINUE
        c.rewrite_status = "FAILED"
        frame = c.frame
        if frame is not None and frame.followup_signal:
            # A reference we could not resolve ("and that one?"): ask, do not guess (D5).
            c.route_info["layer"] = "followup_rule"
            return template("followup_clarify", reason="INPUT_INVALID",
                            rule_id="template.followup_clarify")
        return CONTINUE


class RetrieveStep:
    """Step 8: hybrid retrieval and the gate; below the gate is a refusal without the LLM."""

    name = "retrieve_and_gate"

    def __init__(self, retriever: Retriever, engine: AsyncEngine) -> None:
        self.retriever = retriever
        self.engine = engine

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        assert c.principal is not None and c.frame is not None
        start = time.monotonic()
        async with tenant_tx(self.engine, c.principal.workspace_id, c.principal.user_id) as conn:
            result = await self.retriever.retrieve(conn, c.principal, c.query,
                                                   query_lang=c.frame.lang)
            nearest_ids: list[UUID] = []
            if not result.passed:
                nearest_ids = list(dict.fromkeys(
                    x.document_id for x in result.candidates))[:NEAREST_DOCUMENTS]
            titles = await search.document_titles(conn, c.principal, nearest_ids)
        c.timings["retrieval"] = _ms(start)
        c.retrieval = result
        c.route_info["gate"] = {"score": result.gate_score, "threshold": result.threshold,
                                "mode": result.mode, "passed": result.passed}
        if result.passed:
            c.route_info["refusal"] = None
            return CONTINUE
        c.route_info["refusal"] = "NO_EVIDENCE"
        c.nearest = [{"documentId": str(i), "title": titles[i]} for i in nearest_ids
                     if i in titles]
        # D1: OUT_OF_SCOPE (V2-27) is decided only here, after the gate has refused.
        return refuse("REFUSED_NO_EVIDENCE", template_key="no_evidence", reason="NO_EVIDENCE",
                      rule_id="gate.below_threshold")


class BuildContextStep:
    """Step 9: widen the hit chunks into sections through the access filter (§6.4a)."""

    name = "build_context"

    def __init__(self, engine: AsyncEngine, config: ContextConfig,
                 chain: ChatChain) -> None:
        self.engine, self.config, self.chain = engine, config, chain

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        assert c.principal is not None and c.retrieval is not None
        cfg = self.config
        budget = self.chain.context_budget
        if budget is not None and budget < cfg.max_tokens:
            cfg = replace(cfg, max_tokens=budget)  # a model with a smaller window (§7.4)
        start = time.monotonic()
        async with tenant_tx(self.engine, c.principal.workspace_id, c.principal.user_id) as conn:
            hits = await context_store.load_chunks(
                conn, c.principal, [h.chunk_id for h in c.retrieval.hits])
            groups = (await context_store.load_sections(conn, c.principal, group_keys(hits))
                      if cfg.expand else {})
            infos = await context_store.load_version_info(
                conn, c.principal, list({h.version_id for h in hits}))
        c.timings["context"] = _ms(start)
        c.sources = build_sources(hits, groups, cfg)
        if not c.sources:  # the hits vanished between the search and the read (a delete)
            c.route_info["refusal"] = "NO_EVIDENCE"
            return refuse("REFUSED_NO_EVIDENCE", template_key="no_evidence",
                          reason="NO_EVIDENCE", rule_id="context.empty")
        for s in c.sources:
            info = infos.get(s.version_id) or context_store.VersionInfo(None)
            c.titles[s.version_id] = info.title
            c.source_texts.append(qa_prompt.SourceText(
                n=s.n, text=s.text, title=info.title, page=s.page, code=info.code,
                rev=info.rev, effective=info.effective))
        c.route_info["context"] = {"sources": len(c.sources), "expand": cfg.expand,
                                   "tokens": sum(s.tokens for s in c.sources)}
        return CONTINUE


class BuildPromptStep:
    """Step 10: system rules + sources, and the question in its own message (no history)."""

    name = "build_prompt"

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        assert c.today is not None
        question = c.rewritten or c.text
        original = c.text if c.rewritten else None
        c.prompt = qa_prompt.build_prompt(question=question, sources=c.source_texts, lang=c.lang,
                                          today=c.today, original=original)
        return CONTINUE


class GenerateStep:
    """Step 11: stream the answer through the output guard (canary and prompt echo)."""

    name = "generate_and_stream"

    def __init__(self, chain: ChatChain) -> None:
        self.chain = chain

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        bundle = c.prompt
        assert bundle is not None
        guard = OutputGuard(bundle.canary, bundle.protected)
        tokens = estimate_tokens(" ".join(m["content"] for m in bundle.messages))

        def started(model: str) -> None:
            c.model = model

        start = time.monotonic()
        c.llm_calls += 1
        gen = self.chain.stream(bundle.messages, tokens=tokens, on_start=started)
        stop = threading.Event()
        try:
            async for delta in _pump(gen, stop):
                if "firstDelta" not in c.timings:
                    c.timings["firstDelta"] = _ms(start)
                verdict = guard.feed(delta)
                if verdict.violation:
                    return self._withdraw(c, verdict)
                if verdict.text:
                    c.emit("delta", {"text": verdict.text})
                    c.answer_text = guard.released  # what the client has, kept if the client leaves
            verdict = guard.finish()
            if verdict.violation:
                return self._withdraw(c, verdict)
            if verdict.text:
                c.emit("delta", {"text": verdict.text})
        except LLMError:
            # No model switch after the first delta; keep only the text the client received.
            c.error_code = "LLM_UNAVAILABLE"
            return refuse("ERROR", rule_id="llm.unavailable")
        finally:
            stop.set()  # the reader thread stops after its current read and closes the stream
            c.timings["generate"] = _ms(start)
        c.answer_text = guard.output
        return CONTINUE

    @staticmethod
    def _withdraw(c: QAContext, verdict: Verdict) -> Decision:
        from sopilot_ai.qa import templates

        layer = verdict.violation or "OUTPUT_CANARY"
        c.record(layer, "output.canary" if layer == "OUTPUT_CANARY" else "output.prompt_echo")
        c.replaced = True
        c.emit("replace", {"text": templates.render("guard_block", c.lang), "reason": "GUARD"})
        return refuse("REFUSED_GUARD", template_key="guard_block", rule_id=layer.lower())


class CitationStep:
    """Step 12: drop ``[n]`` that map to no source; one citation per valid ``n`` (§6.4a)."""

    name = "postprocess_citations"

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        valid = {s.n for s in c.sources}
        final, used = qa_citations.clean_markers(c.answer_text, valid)
        c.final_text = final.strip()
        c.citations = qa_citations.build_citations(c.sources, used)
        c.checks["citationCount"] = len(c.citations)
        return CONTINUE


class SelfRefusalStep:
    """Step 13: the model opened with the fixed "not found" sentence (D2)."""

    name = "detect_self_refusal"

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        if not qa_checks.is_generator_not_found(c.final_text):
            return CONTINUE
        c.citations = []  # a refusal cites nothing
        c.checks["citationCount"] = 0
        c.route_info["refusal"] = "GENERATOR_NOT_FOUND"
        return refuse("REFUSED_NO_EVIDENCE", reason="GENERATOR_NOT_FOUND",
                      rule_id="generator.not_found")


class NumberCheckStep:
    """Step 14: flag numbers, dates and amounts no source holds. Flags only, never edits."""

    name = "check_numbers"

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        held = [qa_prompt.render_source(s) for s in c.source_texts]
        held += [t for t in (c.text, c.working_text, c.rewritten) if t]
        if c.today is not None:
            held.append(f"Hôm nay là {c.today.isoformat()}")
        result = qa_checks.check_numbers(c.final_text, held)
        if result.warned:
            c.warnings = result.warnings()
            c.checks["numberWarnings"] = result.to_checks()
        return CONTINUE


def _ctx(ctx: PipelineContext) -> QAContext:
    if not isinstance(ctx, QAContext):
        raise TypeError("the QA steps need a QAContext")
    return ctx

