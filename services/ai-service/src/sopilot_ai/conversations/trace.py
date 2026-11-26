"""Sanitized pipeline trace builder for the Real-time Query Pipeline Inspector.

Maps the 17 execution steps of ``STEP_ORDER`` (plus optional shadow classifier) onto 8 UI stages,
redacts the per-request canary token before any SSE emit or DB write, never echoes raw unmasked
PII into persisted traces, and synthesizes a best-effort trace for pre-V005 historical messages.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sopilot_ai.providers.llm import estimate_tokens
from sopilot_ai.qa import guard as qa_guard
from sopilot_ai.qa.pipeline import Decision, DecisionKind
from sopilot_ai.qa.prompt import PromptBundle

if TYPE_CHECKING:
    from sopilot_ai.conversations.steps import QAContext

REDACTED_CANARY = "[REDACTED_CANARY]"
PREVIEW_CHARS = 180
PROMPT_PREVIEW_CHARS = 320

STAGE_BY_STEP: dict[str, str] = {
    "quota": "input_pii",
    "input": "input_pii",
    "pii": "input_pii",
    "frame": "classify_route",
    "guard": "guard_rule",
    "router": "guard_rule",
    "meaningful_tokens": "guard_rule",
    "semantic_router": "classify_route",
    "setfit_router": "classify_route",
    "setfit_router_shadow": "classify_route",
    "rewrite": "rewrite_translate",
    "translate": "rewrite_translate",
    "retrieve_dense": "retrieve_dense",
    "retrieve_sparse": "retrieve_sparse",
    "retrieve_rrf": "retrieve_rrf",
    "retrieve_rerank": "retrieve_rerank",
    "retrieve_and_gate": "retrieve_rerank",
    "build_context": "context_prompt",
    "build_prompt": "context_prompt",
    "generate_and_stream": "llm_generate",
    "postprocess_citations": "post_checks",
    "detect_self_refusal": "post_checks",
    "check_numbers": "post_checks",
}


def stage_for_step(step_name: str) -> str:
    return STAGE_BY_STEP.get(step_name, "post_checks")


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def redact_prompt_messages(bundle: PromptBundle) -> list[dict[str, str]]:
    """Return a copy of the LLM prompt messages with the per-request canary redacted (FR-13)."""
    canary = bundle.canary
    out: list[dict[str, str]] = []
    for msg in bundle.messages:
        content = msg.get("content", "")
        if canary:
            content = content.replace(canary, REDACTED_CANARY)
        out.append({"role": msg.get("role", "user"), "content": content})
    return out


def _decision_dict(decision: Decision | None) -> dict[str, Any] | None:
    if decision is None or not decision.stops:
        return None
    return {
        "kind": decision.kind.value,
        "outcome": decision.outcome,
        "reason": decision.refusal_reason,
        "ruleId": decision.rule_id,
        "templateKey": decision.template_key,
    }


def _step_status(decision: Decision | None) -> str:
    if decision is None or not decision.stops:
        return "passed"
    if decision.outcome == "ERROR":
        return "error"
    return "blocked"


def _step_summary_and_detail(
    step_name: str, ctx: QAContext, decision: Decision | None
) -> tuple[str, dict[str, Any]]:
    if step_name == "quota":
        res = ctx.reservation
        if res is None:
            return "Quota unlimited", {"enabled": False, "state": "off"}
        state = res.state.value
        detail: dict[str, Any] = {
            "enabled": True,
            "state": state,
            "allowed": res.allowed,
            "userUsed": res.user_used,
            "userLimit": res.user_limit,
            "questionsLeft": res.questions_left,
        }
        if not res.allowed:
            return f"Quota exceeded ({state})", detail
        left = res.questions_left
        summary = f"Quota OK ({left} left today)" if left is not None else "Quota reserved"
        return summary, detail

    if step_name == "input":
        length = len(ctx.text)
        valid = decision is None or not decision.stops
        detail = {
            "charCount": length,
            "maxChars": ctx.max_question_chars,
            "valid": valid,
            "ruleId": decision.rule_id if decision and decision.stops else None,
        }
        if not valid:
            return f"Input rejected ({decision.rule_id if decision else 'invalid'})", detail
        return f"Valid input ({length}/{ctx.max_question_chars} chars)", detail

    if step_name == "pii":
        rules = list(ctx.checks.get("pii") or [])
        detail = {
            "masked": bool(rules),
            "ruleIds": rules,
            "maskedText": ctx.text,
        }
        if rules:
            return f"Masked {len(rules)} PII pattern(s): {', '.join(rules)}", detail
        return "No PII detected", detail

    if step_name == "frame":
        frame = ctx.frame
        if frame is None:
            return "Frame unavailable", {}
        detail = {
            "lang": frame.lang,
            "tokenCount": len(frame.tokens),
            "signals": frame.signals(),
            "short": frame.short,
            "followupMarker": frame.followup_marker,
            "docCodes": sorted(frame.doc_codes),
            "dates": list(frame.dates),
            "amounts": list(frame.amounts),
            "meaningfulTotal": len(frame.meaningful),
        }
        tags = [f"lang={frame.lang}", f"{len(frame.tokens)} tokens"]
        if frame.doc_codes:
            tags.append(f"codes={','.join(sorted(frame.doc_codes))}")
        if frame.followup_signal:
            tags.append("follow-up")
        if frame.comparison:
            tags.append("comparison")
        return "Frame: " + " · ".join(tags), detail

    if step_name == "guard":
        g = ctx.guard
        if g is None:
            return "Guard skipped", {}
        detail = {
            "blocked": g.blocked,
            "blockedRule": g.blocked_rule,
            "blockTemplate": g.block_template,
            "flagRules": list(g.flag_rules),
            "abuseRules": list(g.abuse_rules),
        }
        if g.blocked:
            return f"Blocked by guard ({g.blocked_rule})", detail
        if g.flag_rules or g.abuse_rules:
            flagged = [*g.flag_rules, *g.abuse_rules]
            return f"Flagged ({', '.join(flagged)}), continuing", detail
        return "Input guard clean", detail

    if step_name == "router":
        s = ctx.stripped
        route = ctx.route
        detail = {
            "strippedKinds": list(s.kinds) if s else [],
            "workingText": ctx.working_text,
            "nothingLeft": s.nothing_left if s else False,
            "templateKey": route.template_key if route else None,
        }
        if decision and decision.stops:
            return f"Matched rule template: {decision.template_key}", detail
        if s and s.kinds:
            return f"Stripped {', '.join(s.kinds)}; continuing with cleaned query", detail
        return "No rule template matched", detail

    if step_name == "meaningful_tokens":
        count = ctx.route_info.get("meaningful")
        min_req = qa_guard.min_meaningful_tokens()
        detail = {
            "meaningfulCount": count,
            "minRequired": min_req,
            "templateKey": decision.template_key if decision and decision.stops else None,
        }
        if decision and decision.stops:
            return f"Too few meaningful tokens ({count} < {min_req})", detail
        return f"Meaningful tokens OK ({count} >= {min_req})", detail

    if step_name == "semantic_router":
        sem = ctx.semantic
        if sem is None:
            return "Semantic router off", {"enabled": False}
        info = ctx.route_info.get("semantic") or {}
        detail = {
            "enabled": True,
            "intent": sem.intent,
            "topIntent": sem.top_intent,
            "score": round(sem.top_score, 4),
            "margin": round(sem.margin, 4),
            "decided": bool(decision and decision.stops),
            "templateKey": decision.template_key if decision and decision.stops else None,
            "raw": info,
        }
        if decision and decision.stops:
            return f"Semantic router template: {sem.intent} ({sem.top_score:.2f})", detail
        if sem.intent:
            return (
                f"Semantic: {sem.intent} (score {sem.top_score:.2f}, margin {sem.margin:.2f})",
                detail,
            )
        return f"Semantic: top={sem.top_intent} ({sem.top_score:.2f}), proceeding to RAG", detail

    if step_name in ("setfit_router", "setfit_router_shadow"):
        entry = dict(ctx.route_info.get("classifier") or {})
        mode = entry.get("mode", "shadow" if step_name.endswith("shadow") else "on")
        if entry.get("error"):
            return f"SetFit ({mode}): {entry['error']}", entry
        label = entry.get("label")
        conf = entry.get("confidence")
        action = entry.get("action")
        conf_str = f"{conf * 100:.1f}%" if isinstance(conf, (int, float)) else "n/a"
        if decision and decision.stops:
            return f"SetFit routed to template: {label} ({conf_str})", entry
        suffix = " (shadow)" if mode == "shadow" else ""
        return f"SetFit{suffix}: {label} ({conf_str}) -> {action}", entry

    if step_name == "rewrite":
        original = ctx.working_text or ctx.text
        detail = {
            "historyTurns": len(ctx.history),
            "status": ctx.rewrite_status,
            "originalQuery": original,
            "rewrittenQuery": ctx.rewritten,
        }
        if ctx.rewrite_status == "NONE":
            return "No conversation history; rewrite skipped", detail
        if ctx.rewrite_status == "OK" and ctx.rewritten:
            return f"Rewritten using {len(ctx.history)} prior turn(s)", detail
        if decision and decision.stops:
            return "Follow-up rewrite failed; asking for clarification", detail
        return "Rewrite failed; keeping original query", detail

    if step_name == "translate":
        tr_info = ctx.route_info.get("translate")
        if tr_info is None:
            return "Cross-lingual translation not needed", {"skipped": True, "status": "SKIPPED"}
        detail = {
            "skipped": False,
            "sourceLang": ctx.frame.lang if ctx.frame else ctx.lang,
            "targetLang": tr_info.get("to"),
            "status": tr_info.get("status"),
            "translatedQuery": ctx.alt_query.text if ctx.alt_query else None,
        }
        if ctx.alt_query is not None:
            return f"Translated query -> {ctx.alt_query.lang}", detail
        return f"Translation to {tr_info.get('to')} failed; using original", detail

    if step_name == "retrieve_and_gate":
        r = ctx.retrieval
        if r is None:
            return "Retrieval did not complete", {}
        stats = r.stats
        principal = ctx.principal
        detail = {
            "mode": r.mode,
            "rerankEnabled": stats.rerank_enabled,
            "rerankModel": stats.rerank_model,
            "accessScope": {
                "role": principal.role if principal else None,
                "departmentScoped": bool(
                    principal and principal.role == "MEMBER" and principal.department_id
                ),
            },
            "stats": {
                "denseCount": stats.dense_count,
                "bm25Count": stats.bm25_count,
                "altDenseCount": stats.alt_dense_count,
                "altBm25Count": stats.alt_bm25_count,
                "fusedCount": stats.fused_count,
                "rerankPoolCount": stats.rerank_pool_count,
                "docCodeMatches": stats.doc_code_matches,
                "denseMs": stats.dense_ms,
                "bm25Ms": stats.bm25_ms,
                "rrfMs": stats.rrf_ms,
                "rerankMs": stats.rerank_ms,
            },
            "gateScore": round(r.gate_score, 4) if r.gate_score is not None else None,
            "threshold": round(r.threshold, 4) if r.threshold is not None else None,
            "passed": r.passed,
            "hitCount": len(r.hits),
            "chunkCount": len(ctx.retrieved_chunks),
            "refusal": ctx.route_info.get("refusal"),
            "docCodes": sorted(r.doc_codes),
            "nearestDocuments": list(ctx.nearest),
            "chunks": list(ctx.retrieved_chunks),
            "stageChunks": dict(ctx.stage_chunks),
        }
        score_txt = f"{r.gate_score:.3f}" if r.gate_score is not None else "n/a"
        thr_txt = f"{r.threshold:.3f}" if r.threshold is not None else "n/a"
        prefix = "Reranked & gate" if stats.rerank_enabled else "Gate"
        if r.passed:
            return f"{prefix} passed ({score_txt} >= {thr_txt}) · {len(r.hits)} hit(s)", detail
        refusal = ctx.route_info.get("refusal") or "NO_EVIDENCE"
        return f"{prefix} refused: {refusal} ({score_txt} < {thr_txt})", detail

    if step_name == "build_context":
        sources_detail = []
        for s in ctx.sources:
            st = next((x for x in ctx.source_texts if x.n == s.n), None)
            sources_detail.append({
                "n": s.n,
                "documentId": str(s.document_id),
                "versionId": str(s.version_id),
                "title": ctx.titles.get(s.version_id),
                "page": s.page,
                "sectionPath": list(s.section_path),
                "tokens": s.tokens,
                "reduced": s.reduced,
                "hitChunkCount": len(s.hit_chunk_ids),
                "chunkCount": len(s.chunks),
                "code": st.code if st else None,
                "rev": st.rev if st else None,
                "effective": st.effective if st else None,
            })
        tokens_used = sum(s.tokens for s in ctx.sources)
        ctx_info = ctx.route_info.get("context") or {}
        detail = {
            "sourcesCount": len(ctx.sources),
            "expand": bool(ctx_info.get("expand", True)),
            "tokensUsed": tokens_used,
            "tokenBudget": ctx.context_budget_used,
            "sources": sources_detail,
        }
        if decision and decision.stops:
            return "Context empty after access filter", detail
        return f"Assembled {len(ctx.sources)} source(s) ({tokens_used:,} tokens)", detail

    if step_name == "build_prompt":
        bundle = ctx.prompt
        if bundle is None:
            return "Prompt not built", {}
        messages = redact_prompt_messages(bundle)
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        prompt_tokens_est = estimate_tokens(" ".join(m["content"] for m in messages))
        source = (
            "rewritten" if ctx.rewritten else ("stripped" if ctx.working_text else "original")
        )
        detail = {
            "promptVersion": bundle.prompt_version,
            "questionSource": source,
            "promptTokensEst": prompt_tokens_est,
            "canaryRedacted": True,
            "systemChars": len(system_msg),
            "userChars": len(user_msg),
            "systemPreview": _truncate(system_msg, PROMPT_PREVIEW_CHARS),
            "userMessage": user_msg,
            "messages": messages,
        }
        return f"Fusion prompt ready ({bundle.prompt_version}, ~{prompt_tokens_est:,} tok)", detail

    if step_name == "generate_and_stream":
        prompt_est = (
            estimate_tokens(" ".join(m["content"] for m in ctx.prompt.messages))
            if ctx.prompt
            else 0
        )
        output_est = estimate_tokens(ctx.answer_text) + (ctx.reasoning_chars // 2)
        tokens_in = ctx.tokens_in if ctx.tokens_in is not None else prompt_est
        tokens_out = ctx.tokens_out if ctx.tokens_out is not None else output_est
        detail = {
            "provider": ctx.llm_provider,
            "model": ctx.model,
            "thinkingEnabled": ctx.thinking_enabled,
            "firstReasoningMs": ctx.timings.get("firstReasoning"),
            "reasoningMs": ctx.timings.get("reasoning"),
            "firstDeltaMs": ctx.timings.get("firstDelta"),
            "generateMs": ctx.timings.get("generate"),
            "reasoningChars": ctx.reasoning_chars,
            "answerChars": len(ctx.answer_text),
            "reasoningWithheld": bool(ctx.checks.get("reasoningWithheld")),
            "outputGuard": ctx.output_guard_violation or "passed",
            "promptTokens": tokens_in,
            "outputTokens": tokens_out,
            "usageSource": ctx.usage_source,
            "llmCalls": ctx.llm_calls,
            "errorCode": ctx.error_code,
        }
        if ctx.output_guard_violation:
            return f"OutputGuard blocked stream ({ctx.output_guard_violation})", detail
        if decision and decision.stops:
            return f"Generation failed ({ctx.error_code or 'ERROR'})", detail
        model_lbl = ctx.model or "Modal LLM"
        return f"{model_lbl} ({tokens_in:,} in / {tokens_out:,} out tok)", detail

    if step_name == "postprocess_citations":
        detail = {
            "citationCount": len(ctx.citations),
            "validMarkers": [c.n for c in ctx.citations],
            "invalidMarkersRemoved": ctx.invalid_citations_removed,
        }
        if ctx.invalid_citations_removed:
            return (
                f"{len(ctx.citations)} verified citation(s), "
                f"{ctx.invalid_citations_removed} invalid stripped"
            ), detail
        return f"{len(ctx.citations)} verified citation(s)", detail

    if step_name == "detect_self_refusal":
        detected = bool(decision and decision.stops)
        detail = {"detected": detected}
        if detected:
            return "Model self-refusal detected (GENERATOR_NOT_FOUND)", detail
        return "No self-refusal detected", detail

    if step_name == "check_numbers":
        detail = {
            "warned": bool(ctx.warnings),
            "warnings": list(ctx.warnings),
        }
        if ctx.warnings:
            total_vals = sum(len(w.get("values") or []) for w in ctx.warnings)
            return f"Flagged {total_vals} ungrounded numeric value(s)", detail
        return "All numbers grounded in sources", detail

    return f"Completed {step_name}", {}


@dataclass
class TraceCollector:
    """Accumulates step snapshots for one question and produces SSE & persisted payloads."""

    message_id: UUID
    conversation_id: UUID
    mode: str
    lang: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    prompt_messages: list[dict[str, str]] | None = None

    def step_started(self, step_name: str) -> dict[str, Any]:
        return {
            "step": step_name,
            "stage": stage_for_step(step_name),
            "status": "running",
        }

    def step_progress(
        self, step_name: str, *, summary: str, detail: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "step": step_name,
            "stage": stage_for_step(step_name),
            "status": "running",
            "summary": summary,
            "detail": detail,
        }

    def record_phase(
        self,
        phase_name: str,
        status: str,
        duration_ms: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build (and persist if terminal) a retrieval sub-phase event."""
        d = dict(detail or {})
        summary = _phase_summary(phase_name, status, d)
        payload: dict[str, Any] = {
            "step": phase_name,
            "stage": stage_for_step(phase_name),
            "status": status,
            "summary": summary,
        }
        if duration_ms is not None:
            payload["durationMs"] = duration_ms
        if d:
            payload["detail"] = d
        if status in ("passed", "skipped") and phase_name != "retrieve_rerank":
            self.steps.append(payload)
        return payload

    def step_finished(
        self,
        step_name: str,
        ctx: QAContext,
        decision: Decision | None,
        duration_ms: int,
    ) -> dict[str, Any]:
        summary, detail = _step_summary_and_detail(step_name, ctx, decision)
        payload: dict[str, Any] = {
            "step": step_name,
            "stage": stage_for_step(step_name),
            "status": _step_status(decision),
            "durationMs": duration_ms,
            "decision": _decision_dict(decision),
            "summary": summary,
            "detail": detail,
        }
        if step_name == "build_prompt" and isinstance(detail.get("messages"), list):
            self.prompt_messages = detail["messages"]
        self.steps.append(payload)
        return payload

    def step_errored(self, step_name: str, error_code: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "step": step_name,
            "stage": stage_for_step(step_name),
            "status": "error",
            "decision": {
                "kind": DecisionKind.REFUSE.value,
                "outcome": "ERROR",
                "reason": None,
                "ruleId": error_code.lower(),
            },
            "summary": f"Step failed ({error_code})",
            "detail": {"errorCode": error_code},
        }
        self.steps.append(payload)
        return payload

    def to_persisted_json(
        self,
        *,
        outcome: str,
        refusal_reason: str | None,
        total_ms: int,
        disclaimers: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Sanitized JSON stored in ``rag.message_traces.trace``.

        Retrieved chunk bodies are stripped here and hydrated live through ``allowed_cte()`` on
        read, so revoked/deleted documents can never leak from stored traces.
        """
        stored_steps: list[dict[str, Any]] = []
        for entry in self.steps:
            detail = dict(entry.get("detail") or {})
            if entry.get("step") == "retrieve_and_gate":
                detail.pop("chunks", None)
                detail.pop("stageChunks", None)
            elif entry.get("step") == "build_prompt":
                detail.pop("messages", None)  # stored once at top-level promptMessages
            stored_steps.append({**entry, "detail": detail})
        return {
            "version": 1,
            "mode": self.mode,
            "lang": self.lang,
            "outcome": outcome,
            "refusalReason": refusal_reason,
            "totalMs": total_ms,
            "disclaimers": list(disclaimers),
            "steps": stored_steps,
            "promptMessages": self.prompt_messages,
        }


def _phase_summary(phase_name: str, status: str, detail: dict[str, Any]) -> str:
    if status == "running":
        labels = {
            "retrieve_dense": "Searching dense vector index…",
            "retrieve_sparse": "Searching BM25 lexical index…",
            "retrieve_rrf": "Fusing rankings with RRF…",
            "retrieve_rerank": "Reranking candidates & checking gate…",
        }
        return labels.get(phase_name, f"Running {phase_name}…")
    if status == "skipped":
        if detail.get("reason") == "rerank_off_by_request":
            return "Reranking turned off for this question"
        return "Skipped by retrieval mode"
    if phase_name == "retrieve_dense":
        total = int(detail.get("denseCount") or 0) + int(detail.get("altDenseCount") or 0)
        top = detail.get("topScore")
        top_txt = f" · top {top:.3f}" if isinstance(top, (int, float)) else ""
        return f"{total} dense candidate(s){top_txt}"
    if phase_name == "retrieve_sparse":
        total = int(detail.get("bm25Count") or 0) + int(detail.get("altBm25Count") or 0)
        terms = int(detail.get("termCount") or 0)
        return f"{total} BM25 candidate(s) · {terms} lexical term(s)"
    if phase_name == "retrieve_rrf":
        fused = int(detail.get("fusedCount") or 0)
        pool = int(detail.get("poolCount") or 0)
        boosts = int(detail.get("docCodeMatches") or 0)
        boost_txt = f" · {boosts} code boost" if boosts else ""
        return f"Fused {fused} → top {pool} pool (k={detail.get('rrfK', 60)}){boost_txt}"
    return f"Completed {phase_name}"


def strip_document_data(trace: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Fail-closed redaction when any source document is deleted or access-revoked (FR-19/25)."""
    safe_steps: list[dict[str, Any]] = []
    for entry in trace.get("steps") or []:
        stage = entry.get("stage")
        if stage in (
            "retrieve_dense",
            "retrieve_sparse",
            "retrieve_rrf",
            "retrieve_rerank",
            "context_prompt",
            "llm_generate",
            "post_checks",
        ):
            safe_steps.append({
                "step": entry.get("step"),
                "stage": stage,
                "status": entry.get("status", "passed"),
                "durationMs": entry.get("durationMs"),
                "summary": "Hidden because a source document is no longer accessible",
                "detail": {"hidden": True},
            })
        else:
            safe_steps.append(entry)
    return {
        **trace,
        "hidden": True,
        "hiddenReason": reason,
        "steps": safe_steps,
        "chunks": [],
        "stageChunks": {},
        "promptMessages": None,
    }


def synthesize_legacy_trace(
    *,
    message_id: UUID,
    conversation_id: UUID,
    row: Any,
    guard_events: Sequence[Any],
    citations_count: int,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Best-effort trace reconstruction for historical messages written before V005."""
    route = row.route or {}
    checks = row.checks or {}
    latency = row.latency_ms or {}
    step_names: list[str] = list(route.get("steps") or [])
    decided_by: str | None = route.get("decided_by")
    steps: list[dict[str, Any]] = []

    for name in step_names:
        is_decider = decided_by == name
        status = (
            "error"
            if is_decider and row.outcome == "ERROR"
            else ("blocked" if is_decider else "passed")
        )
        detail: dict[str, Any] = {}
        summary = f"Completed {name}"
        dur: int | None = None

        if name == "pii":
            rules = list(checks.get("pii") or [])
            detail = {"masked": bool(rules), "ruleIds": rules}
            summary = f"Masked {len(rules)} PII pattern(s)" if rules else "No PII detected"
        elif name == "frame":
            detail = {"lang": route.get("lang") or row.lang, "signals": route.get("signals") or {}}
            summary = f"Frame: lang={detail['lang']}"
        elif name == "guard":
            flags = [g.rule_id for g in guard_events if g.layer == "INPUT_FLAG"]
            blocks = [g.rule_id for g in guard_events if g.layer == "INPUT_BLOCK"]
            detail = {"blocked": bool(blocks), "blockedRule": blocks[0] if blocks else None,
                      "flagRules": flags}
            summary = f"Blocked ({blocks[0]})" if blocks else "Input guard clean"
        elif name == "router":
            detail = {"strippedKinds": route.get("stripped") or [],
                      "templateKey": route.get("intent") if is_decider else None}
            summary = (f"Matched rule template: {route.get('intent')}"
                       if is_decider else "No rule template matched")
        elif name == "meaningful_tokens":
            detail = {"meaningfulCount": route.get("meaningful")}
            summary = f"Meaningful tokens: {route.get('meaningful')}"
        elif name == "semantic_router":
            dur = latency.get("router")
            sem = route.get("semantic") or {}
            detail = {"enabled": True, **sem}
            summary = f"Semantic: {sem.get('intent') or sem.get('topIntent') or 'RAG'}"
        elif name == "setfit_router":
            dur = latency.get("classifier")
            clf = route.get("classifier") or {}
            detail = clf
            summary = f"SetFit: {clf.get('label', 'n/a')}"
        elif name == "rewrite":
            dur = latency.get("rewrite")
            detail = {"status": row.rewrite_status, "rewrittenQuery": row.standalone_query}
            summary = f"Rewrite: {row.rewrite_status}"
        elif name == "translate":
            dur = latency.get("translate")
            tr = route.get("translate")
            detail = tr or {"skipped": True, "status": "SKIPPED"}
            summary = f"Translate -> {tr.get('to')}" if tr else "Translation skipped"
        elif name == "retrieve_and_gate":
            dur = latency.get("retrieval")
            gate = route.get("gate") or {}
            detail = {
                "mode": row.retrieval_mode or gate.get("mode"),
                "gateScore": row.gate_score,
                "threshold": row.threshold,
                "passed": gate.get("passed"),
                "refusal": route.get("refusal"),
                "hitCount": sum(1 for c in chunks if c.get("inContext")),
            }
            summary = (
                f"Gate passed ({row.gate_score:.3f})"
                if gate.get("passed") and row.gate_score is not None
                else f"Gate refused ({route.get('refusal') or 'NO_EVIDENCE'})"
            )
        elif name == "build_context":
            dur = latency.get("context")
            cinfo = route.get("context") or {}
            detail = {
                "sourcesCount": cinfo.get("sources", len(row.context_sources or [])),
                "expand": cinfo.get("expand", True),
                "tokensUsed": cinfo.get("tokens", 0),
                "sources": row.context_sources or [],
            }
            summary = f"Assembled {detail['sourcesCount']} source(s)"
        elif name == "build_prompt":
            detail = {"promptVersion": row.prompt_version, "canaryRedacted": True}
            summary = f"Prompt {row.prompt_version or 'qa-v1'} (snapshot not stored)"
        elif name == "generate_and_stream":
            dur = latency.get("generate")
            detail = {
                "provider": "modal",
                "model": row.model,
                "firstReasoningMs": latency.get("firstReasoning"),
                "reasoningMs": latency.get("reasoning"),
                "firstDeltaMs": latency.get("firstDelta"),
                "generateMs": latency.get("generate"),
                "promptTokens": row.tokens_in,
                "outputTokens": row.tokens_out,
                "usageSource": "provider" if row.tokens_in is not None else "estimated",
                "llmCalls": route.get("llmCalls", 1),
                "outputGuard": next(
                    (g.layer for g in guard_events
                     if g.layer in ("OUTPUT_CANARY", "OUTPUT_PROMPT_ECHO")),
                    "passed",
                ),
            }
            summary = row.model or "LLM generation"
        elif name == "postprocess_citations":
            detail = {"citationCount": citations_count}
            summary = f"{citations_count} verified citation(s)"
        elif name == "detect_self_refusal":
            detail = {"detected": is_decider}
            summary = "Self-refusal detected" if is_decider else "No self-refusal"
        elif name == "check_numbers":
            nw = checks.get("numberWarnings")
            detail = {"warned": bool(nw), "warnings": nw or []}
            summary = "Number warnings flagged" if nw else "All numbers grounded"

        steps.append({
            "step": name,
            "stage": stage_for_step(name),
            "status": status,
            "durationMs": dur,
            "decision": (
                {"kind": "refuse", "outcome": row.outcome, "reason": row.refusal_reason}
                if is_decider
                else None
            ),
            "summary": summary,
            "detail": detail,
        })

    return {
        "version": 1,
        "messageId": str(message_id),
        "conversationId": str(conversation_id),
        "mode": row.retrieval_mode or "hybrid",
        "lang": row.lang or "vi",
        "outcome": row.outcome,
        "refusalReason": row.refusal_reason,
        "totalMs": latency.get("total"),
        "disclaimers": list(checks.get("disclaimers") or []),
        "reconstructed": True,
        "hidden": False,
        "hiddenReason": None,
        "steps": steps,
        "chunks": chunks,
        "promptMessages": None,
    }
