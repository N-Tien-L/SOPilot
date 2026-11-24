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
import inspect
import re
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Protocol
from uuid import UUID

import numpy as np
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.conversations import repository as conv_repo
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.providers.llm import LLMError, Thought, estimate_tokens
from sopilot_ai.qa import checks as qa_checks
from sopilot_ai.qa import citations as qa_citations
from sopilot_ai.qa import prompt as qa_prompt
from sopilot_ai.qa import router as qa_router
from sopilot_ai.qa import setfit_router
from sopilot_ai.qa import translate as qa_translate
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
from sopilot_ai.retrieval.retriever import AltQuery, PhaseHook, RetrievalResult, Retriever

NEAREST_DOCUMENTS = 3

log = structlog.get_logger(__name__)


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
    conversation_id: UUID | None = None  # None for a new conversation
    emit: Callable[[str, Any], None] = field(default=lambda name, data: None, repr=False)

    reservation: Reservation | None = None
    semantic: qa_router.SemanticDecision | None = None  # V2-27; None when the router is off
    query_vector: np.ndarray | None = None  # router vector of ``text``, reused without history
    classifier: setfit_router.ClassifierDecision | None = None  # V2-44; None when off or failed
    classifier_off_topic: bool = False  # mode ``on``: OUT_OF_SCOPE if the gate refuses (D1)
    rewritten: str | None = None
    rewrite_status: str = "NONE"
    alt_query: AltQuery | None = None  # the question in the other language (§6.4b)
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

    # Pipeline Inspector fields (populated by steps; never logged)
    emit_trace: bool = False
    on_retrieval_phase: PhaseHook | None = field(default=None, repr=False)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    context_budget_used: int | None = None
    invalid_citations_removed: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    usage_source: str = "estimated"
    reasoning_chars: int = 0
    output_guard_violation: str | None = None
    thinking_enabled: bool = False
    llm_provider: str = "modal"

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
            yield value  # unchanged: a Thought must stay a Thought for GenerateStep (V2-42)
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


class SemanticRouterStep:
    """Step 6b (V2-27): embedding router, only on questions the rules left undecided.

    Never calls an LLM and never blocks. Present in the chain only when
    ``SOPILOT_SEMANTIC_ROUTER_ENABLED`` is true, so with the flag off the chain is V2-10's.
    It embeds the masked original question (not the rewrite) and records its decision in
    ``messages.route.semantic``. Template intents answer with a fixed sentence (``TEMPLATE``,
    free); disclaimer intents still run RAG; ``off_topic`` only matters if the gate refuses.
    """

    name = "semantic_router"

    def __init__(self, layer: qa_router.SemanticLayer, engine: AsyncEngine) -> None:
        self.layer = layer
        self.engine = engine

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        start = time.monotonic()
        vector = await asyncio.to_thread(self.layer.embed_query, c.text)
        decision = self.layer.decide(vector, has_history=bool(c.history))
        c.timings["router"] = _ms(start)
        c.semantic = decision
        if not c.history:
            c.query_vector = vector
        c.route_info["semantic"] = {
            "layer": "semantic", "intent": decision.intent, "topIntent": decision.top_intent,
            "score": round(decision.top_score, 4), "margin": round(decision.margin, 4)}
        intent = decision.intent
        action = qa_router.action_for(intent)
        if intent is None or action == qa_router.ACTION_RAG:
            return CONTINUE
        if action == qa_router.ACTION_DISCLAIMER:
            c.checks.setdefault("disclaimers", []).append(intent)
            return CONTINUE
        if action == qa_router.ACTION_OUT_OF_SCOPE:
            return CONTINUE  # decided by RetrieveStep, after the gate
        c.route_info["layer"] = "semantic"
        c.route_info["intent"] = intent
        if intent == qa_router.KIND_ABUSE:
            c.record("INPUT_FLAG", "router.abuse")
        if intent in qa_router.HISTORY_INTENTS:
            return await self._about_source(c)
        return template(intent, rule_id=f"router.{intent}")

    async def _about_source(self, c: QAContext) -> Decision:
        sources: list[tuple[str, int | None]] = []
        if c.conversation_id is not None and c.principal is not None:
            async with tenant_tx(self.engine, c.principal.workspace_id,
                                 c.principal.user_id) as conn:
                sources = await conv_repo.previous_sources(conn, c.principal, c.conversation_id)
        if not sources:
            return template("about_source_none", rule_id="router.about_source")
        page_word = "trang" if c.lang == "vi" else "page"
        lines = "\n".join(f"- {t}" + (f", {page_word} {p}" if p else "") for t, p in sources)
        return template("about_source", rule_id="router.about_source", sources=lines)


async def classify_question(classifier: setfit_router.SetFitClassifier, c: QAContext,
                            mode: str) -> setfit_router.ClassifierDecision | None:
    """Run the SetFit classifier on the masked question and the previous turn (V2-44).

    Records the prediction in ``messages.route.classifier`` (label, confidence, action, the
    previous-message flag and the time). A failure never blocks the question: it is recorded as a
    fixed code and the question goes on to retrieval. Question text and model output are never
    logged.
    """
    start = time.monotonic()
    entry: dict[str, Any] = {"layer": "setfit", "mode": mode, "withPrevious": False}
    try:
        previous = setfit_router.previous_message(c.history, classifier.spec.previous_max_chars)
        entry["withPrevious"] = previous is not None
        decision = await asyncio.to_thread(classifier.classify, c.text, previous)
    except Exception as exc:  # noqa: BLE001 - the client never sees it; only the type is logged
        log.warning("router_classifier_failed", error=type(exc).__name__)
        entry["error"] = "CLASSIFIER_ERROR"
        c.route_info["classifier"] = entry
        return None
    c.timings["classifier"] = _ms(start)
    c.classifier = decision
    entry.update({"label": decision.label, "confidence": round(decision.confidence, 4),
                  "action": decision.action})
    c.route_info["classifier"] = entry
    return decision


class ClassifierRouterStep:
    """Step 6c (V2-44, mode ``on``): the SetFit classifier replaces the cosine comparison.

    Runs after the rules, on questions they left undecided, and never blocks. Template labels
    (greeting, thanks, about_bot, abuse_only) answer with a fixed sentence; disclaimer labels still
    run retrieval and add the disclaimer; ``off_topic`` only matters if the gate refuses. Every
    other label, deferred or not, goes to retrieval. No confidence threshold (ADR-012 §2).
    """

    name = "setfit_router"

    def __init__(self, classifier: setfit_router.SetFitClassifier) -> None:
        self.classifier = classifier

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        decision = await classify_question(self.classifier, c, "on")
        if decision is None or decision.action == qa_router.ACTION_RAG:
            return CONTINUE
        if decision.action == qa_router.ACTION_DISCLAIMER:
            c.checks.setdefault("disclaimers", []).append(decision.label)
            return CONTINUE
        if decision.action == qa_router.ACTION_OUT_OF_SCOPE:
            c.classifier_off_topic = True  # decided by RetrieveStep, after the gate
            return CONTINUE
        c.route_info["layer"] = "setfit"
        c.route_info["intent"] = decision.label
        if decision.label == qa_router.KIND_ABUSE:
            c.record("INPUT_FLAG", "router.abuse")
        return template(decision.label, rule_id=f"router.{decision.label}")


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


class TranslateStep:
    """Step 7b (§6.4b): also ask the question in the language of the documents.

    Multilingual embeddings and rerankers score a question and a passage in two languages far
    lower than in one: measured on 15 answerable questions over English pages, the Vietnamese form
    passed the rerank gate 6 times and the English form 15 times. When the other of vi/en holds
    enough of the documents the asker can read, one short call of the rewrite model gives the
    question in that language and retrieval uses both. A failed call keeps the original question.
    """

    name = "translate"

    def __init__(self, chain: ChatChain, engine: AsyncEngine, min_share: float | None) -> None:
        self.chain = chain
        self.engine = engine
        self.min_share = min_share

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        if self.min_share is None or c.frame is None or c.principal is None:
            return CONTINUE
        if c.frame.lang not in qa_translate.SUPPORTED or not c.query.strip():
            return CONTINUE
        async with tenant_tx(self.engine, c.principal.workspace_id, c.principal.user_id) as conn:
            doc_langs = await search.document_languages(conn, c.principal)
        target = qa_translate.translation_target(c.frame.lang, doc_langs,
                                                 min_share=self.min_share)
        if target is None:
            return CONTINUE
        messages = qa_translate.build_translate_prompt(c.query, target)
        tokens = estimate_tokens(" ".join(m["content"] for m in messages))
        start = time.monotonic()
        c.llm_calls += 1
        translated: str | None = None
        try:
            raw = await asyncio.to_thread(self.chain.complete, messages, tokens=tokens,
                                          temperature=0.0)
            translated = qa_prompt.clean_rewrite(raw, max_chars=c.max_question_chars)
        except LLMError:
            translated = None
        c.timings["translate"] = _ms(start)
        if translated and translated.casefold() != c.query.casefold():
            c.alt_query = AltQuery(translated, target)
            c.route_info["translate"] = {"to": target, "status": "OK"}
        else:
            c.route_info["translate"] = {"to": target, "status": "FAILED"}
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
            # The router's vector is reused only when retrieval searches exactly that text
            # (no history, nothing stripped); otherwise the query is embedded as before.
            reuse = c.query_vector if c.query_vector is not None and c.query == c.text else None
            result = await self.retriever.retrieve(conn, c.principal, c.query,
                                                   query_lang=c.frame.lang, query_vector=reuse,
                                                   alt=c.alt_query, on_phase=c.on_retrieval_phase)
            nearest_ids: list[UUID] = []
            if not result.passed:
                nearest_ids = list(dict.fromkeys(
                    x.document_id for x in result.candidates))[:NEAREST_DOCUMENTS]
            cand_doc_ids = list(dict.fromkeys([
                *(x.document_id for x in result.candidates),
                *nearest_ids,
            ]))
            titles = await search.document_titles(conn, c.principal, cand_doc_ids)
            loaded = await context_store.load_chunks(
                conn, c.principal, [x.chunk_id for x in result.candidates])
        c.timings["retrieval"] = _ms(start)
        c.retrieval = result
        hit_ids = {h.chunk_id for h in result.hits}
        by_chunk_id = {ch.chunk_id: ch for ch in loaded}
        c.retrieved_chunks = []
        for cand in result.candidates:
            ch = by_chunk_id.get(cand.chunk_id)
            if ch is None:
                continue
            clean_preview = " ".join(ch.content.split())
            preview = (clean_preview[:180].rstrip() + "…"
                       if len(clean_preview) > 180 else clean_preview)
            c.retrieved_chunks.append({
                "rank": cand.rank,
                "chunkId": str(cand.chunk_id),
                "documentId": str(cand.document_id),
                "versionId": str(cand.version_id),
                "title": titles.get(cand.document_id),
                "sectionPath": list(ch.section_path),
                "page": ch.page_start,
                "chunkType": ch.chunk_type,
                "tokenCount": ch.token_count,
                "denseScore": round(cand.dense_score, 4) if cand.dense_score is not None else None,
                "bm25Score": round(cand.bm25_score, 4) if cand.bm25_score is not None else None,
                "fusionScore": (round(cand.fusion_score, 4)
                                if cand.fusion_score is not None else None),
                "rerankScore": (round(cand.rerank_score, 4)
                                if cand.rerank_score is not None else None),
                "docCodeMatch": cand.doc_code_match,
                "inContext": cand.chunk_id in hit_ids,
                "preview": preview,
                "content": ch.content,
            })
        c.route_info["gate"] = {"score": result.gate_score, "threshold": result.threshold,
                                "mode": result.mode, "passed": result.passed}
        if result.passed:
            c.route_info["refusal"] = None
            return CONTINUE
        # D1: OUT_OF_SCOPE (V2-27) is decided only here, after the gate has refused: same
        # sentence, no nearest documents, and never on the knowledge-gap list.
        if c.classifier_off_topic or (
                c.semantic is not None
                and qa_router.is_out_of_scope(c.semantic, gate_refused=True)):
            c.route_info["refusal"] = "OUT_OF_SCOPE"
            return refuse("REFUSED_NO_EVIDENCE", template_key="no_evidence",
                          reason="OUT_OF_SCOPE", rule_id="router.off_topic")
        c.route_info["refusal"] = "NO_EVIDENCE"
        c.nearest = [{"documentId": str(i), "title": titles[i]} for i in nearest_ids
                     if i in titles]
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
        c.context_budget_used = cfg.max_tokens
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
        # The same question retrieval searched: the model never sees words the router stripped.
        base = c.working_text or c.text
        question = c.rewritten or base
        original = base if c.rewritten else None
        # Lengths only, never the text: the question is user content (see classify_question).
        source = "rewritten" if c.rewritten else ("stripped" if c.working_text else "original")
        log.info("prompt_question_selected",
                 source=source,
                 question_chars=len(question), original_chars=len(c.text),
                 stripped_chars=len(c.text) - len(base))
        c.prompt = qa_prompt.build_prompt(question=question, sources=c.source_texts, lang=c.lang,
                                          today=c.today, original=original)
        return CONTINUE


class _ThoughtStream:
    """Forwards the model's reasoning as ``reasoning`` events and times it.

    ``timings``: ``firstReasoning`` (ms to the first reasoning text) and ``reasoning`` (ms from
    the request to the end of the reasoning). ``reasoning_done`` carries the same duration so the
    client can show "Thought for N s".
    """

    def __init__(self, c: QAContext, guard: OutputGuard, start: float) -> None:
        self.c, self.guard, self.start = c, guard, start
        self.active = False
        self.withheld = False

    def feed(self, text: str) -> None:
        if "firstReasoning" not in self.c.timings:
            self.c.timings["firstReasoning"] = _ms(self.start)
        self.active = True
        if self.withheld:
            return
        verdict = self.guard.feed(text)
        if verdict.violation:
            self._withhold()
        elif verdict.text:
            self.c.emit("reasoning", {"text": verdict.text})

    def close(self) -> None:
        """Called at the first answer text and at the end of the stream; only the first counts."""
        if not self.active:
            return
        self.active = False
        if not self.withheld:
            verdict = self.guard.finish()
            if verdict.violation:
                self._withhold()
            elif verdict.text:
                self.c.emit("reasoning", {"text": verdict.text})
        ms = _ms(self.start)
        self.c.timings["reasoning"] = ms
        self.c.emit("reasoning_done", {"durationMs": ms})

    def _withhold(self) -> None:
        self.withheld = True
        self.c.checks["reasoningWithheld"] = True


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

        clients = getattr(self.chain, "clients", None)
        if clients:
            first_spec = getattr(clients[0], "spec", None)
            if first_spec is not None:
                c.llm_provider = getattr(first_spec, "provider", "modal") or "modal"
                c.thinking_enabled = bool(getattr(first_spec, "thinking", False))

        def started(model: str) -> None:
            c.model = model
            if c.emit_trace:
                c.emit("step", {
                    "step": self.name,
                    "stage": "llm_generate",
                    "status": "running",
                    "summary": f"Streaming from {model} ({c.llm_provider})",
                    "detail": {
                        "provider": c.llm_provider,
                        "model": model,
                        "thinkingEnabled": c.thinking_enabled,
                    },
                })

        def got_usage(prompt_tok: int, completion_tok: int) -> None:
            c.tokens_in = prompt_tok
            c.tokens_out = completion_tok
            c.usage_source = "provider"

        # Reasoning has its own guard. A thinking model often quotes its instructions, so a hit
        # here withholds the reasoning (never the answer); the answer guard below stays strict.
        start = time.monotonic()
        thought = _ThoughtStream(c, OutputGuard(bundle.canary, bundle.protected), start)
        c.llm_calls += 1
        stream_kwargs: dict[str, Any] = {"tokens": tokens, "on_start": started}
        if "on_usage" in inspect.signature(self.chain.stream).parameters:
            stream_kwargs["on_usage"] = got_usage
        gen = self.chain.stream(bundle.messages, **stream_kwargs)
        stop = threading.Event()
        reasoning_chars = 0
        try:
            async for delta in _pump(gen, stop):
                if isinstance(delta, Thought):
                    reasoning_chars += len(delta)
                    c.reasoning_chars = reasoning_chars
                    thought.feed(str(delta))
                    continue
                thought.close()
                if "firstDelta" not in c.timings:
                    c.timings["firstDelta"] = _ms(start)
                verdict = guard.feed(delta)
                if verdict.violation:
                    return self._withdraw(c, verdict)
                if verdict.text:
                    c.emit("delta", {"text": verdict.text})
                    c.answer_text = guard.released  # what the client has, kept if the client leaves
            thought.close()
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
        if not guard.output.strip():
            # V2-43: the output ceiling ran out inside the reasoning (or the model said nothing).
            # No answer is not an answer: end as an error, never ANSWERED with empty text.
            log.warning("answer_empty", reasoning_chars=reasoning_chars, model=c.model)
            c.checks["emptyAnswer"] = True
            c.error_code = "LLM_UNAVAILABLE"
            return refuse("ERROR", rule_id="llm.empty_answer")
        c.answer_text = guard.output
        return CONTINUE

    @staticmethod
    def _withdraw(c: QAContext, verdict: Verdict) -> Decision:
        from sopilot_ai.qa import templates

        layer = verdict.violation or "OUTPUT_CANARY"
        c.output_guard_violation = layer
        c.record(layer, "output.canary" if layer == "OUTPUT_CANARY" else "output.prompt_echo")
        c.replaced = True
        c.emit("replace", {"text": templates.render("guard_block", c.lang), "reason": "GUARD"})
        return refuse("REFUSED_GUARD", template_key="guard_block", rule_id=layer.lower())


_CITE_MARKER = re.compile(r"\[(\d+)\]")


class CitationStep:
    """Step 12: drop ``[n]`` that map to no source; one citation per valid ``n`` (§6.4a)."""

    name = "postprocess_citations"

    async def run(self, ctx: PipelineContext) -> Decision:
        c = _ctx(ctx)
        valid = {s.n for s in c.sources}
        raw_markers = [int(m.group(1)) for m in _CITE_MARKER.finditer(c.answer_text)]
        c.invalid_citations_removed = sum(1 for n in raw_markers if n not in valid)
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
        log.info("self_refusal_detected", citations_dropped=len(c.citations))
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

