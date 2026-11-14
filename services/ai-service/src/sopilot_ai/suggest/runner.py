"""Run one metadata-suggestion job (V2-25, TECH-V2-ai-service §5.7).

Order: rules first (title), then the cache, then one LLM call with a single retry under a timeout.
If the model still fails, the job keeps the rule result with ``method = RULES_FALLBACK``. The result
goes to core-api through the outbox (``SUGGESTIONS_READY``); nothing here edits the document.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.db.engine import system_tx, tenant_tx
from sopilot_ai.db.repositories import outbox, suggestions
from sopilot_ai.db.repositories.suggestions import ClaimedSuggestion
from sopilot_ai.providers.llm import LLMChain, LLMError, estimate_tokens
from sopilot_ai.suggest import llm as sllm
from sopilot_ai.suggest import rules

log = structlog.get_logger(__name__)

MAX_ATTEMPTS = 3  # a lease that expired this many times is a failed job, not an endless retry


class SuggestDeps:
    def __init__(self, engine: AsyncEngine, chain: LLMChain | None, model: str, *,
                 max_input_tokens: int = 1500, model_attempts: int = 2,
                 max_output_tokens: int = 400) -> None:
        self.engine = engine
        self.chain = chain  # None: no usable model configured, rules only
        self.model = model
        self.max_input_tokens = max_input_tokens
        self.model_attempts = model_attempts
        self.max_output_tokens = max_output_tokens


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


async def _ask_model(deps: SuggestDeps, messages: list[dict[str, str]], category_ids: set[str],
                     timings: dict[str, Any]) -> tuple[sllm.Suggestion, str]:
    assert deps.chain is not None
    tokens_in = sum(estimate_tokens(m["content"]) for m in messages)
    for _ in range(deps.model_attempts):
        timings["attempts"] = timings.get("attempts", 0) + 1
        started = time.perf_counter()
        try:
            raw = await asyncio.to_thread(deps.chain.complete, messages,
                                          tokens=tokens_in + deps.max_output_tokens, temperature=0)
        except (LLMError, httpx.HTTPError) as exc:
            timings["llm_ms"] = timings.get("llm_ms", 0) + _ms(started)
            log.warning("suggest_model_failed", error=type(exc).__name__)
            continue
        timings["llm_ms"] = timings.get("llm_ms", 0) + _ms(started)
        try:
            suggestion = sllm.parse_output(raw, category_ids)
        except ValueError:
            log.warning("suggest_output_invalid")
            continue
        timings["tokens_in"] = tokens_in  # estimates: the chain returns text, not usage
        timings["tokens_out"] = estimate_tokens(raw)
        return suggestion, "LLM"
    return sllm.Suggestion(), "RULES_FALLBACK"


async def handle(job: ClaimedSuggestion, deps: SuggestDeps) -> str:
    """Process ``job``; returns the resulting status (for logs and tests)."""
    started = time.perf_counter()
    bound = log.bind(suggestion_job=str(job.id), version_id=str(job.version_id))
    if job.attempts > MAX_ATTEMPTS:
        async with tenant_tx(deps.engine, job.workspace_id) as conn:
            await suggestions.finish(conn, job, status="FAILED", result=None, method=None,
                                     timings={"reason": "lease_expired_too_often"})
        bound.error("suggest_retry_exhausted")
        return "FAILED"

    inp = job.input
    file_title = str(inp.get("title") or "")
    file_sha = str(inp.get("sha256") or "")
    categories = [{"id": str(c["id"]), "name": str(c["name"])} for c in inp.get("categories", [])]
    tags = [str(t) for t in inp.get("tags", [])]

    async with tenant_tx(deps.engine, job.workspace_id) as conn:
        extracted = await suggestions.extracted_text(conn, job.workspace_id, job.version_id)
    if extracted is None:
        async with tenant_tx(deps.engine, job.workspace_id) as conn:
            await suggestions.finish(conn, job, status="FAILED", result=None, method=None,
                                     timings={"reason": "no_extracted_text"})
        bound.error("suggest_no_extracted_text")
        return "FAILED"

    title = rules.title_candidate(extracted.markdown, file_title)
    key = sllm.cache_key(job.workspace_id, file_sha, deps.model, categories)
    timings: dict[str, Any] = {"cache_hit": False}
    async with tenant_tx(deps.engine, job.workspace_id) as conn:
        cached = await suggestions.cache_get(conn, job.workspace_id, key)

    if cached is not None:
        timings["cache_hit"] = True
        suggestion, method = sllm.Suggestion(**cached["suggestion"]), "LLM"
    elif deps.chain is None:
        suggestion, method = sllm.Suggestion(), "RULES_FALLBACK"
    else:
        messages = sllm.build_messages(file_title, extracted.markdown, categories, tags,
                                       deps.max_input_tokens)
        suggestion, method = await _ask_model(deps, messages, {c["id"] for c in categories},
                                              timings)

    result = {"title": title, "description": suggestion.description,
              "categoryId": suggestion.category_id,
              "proposedCategoryName": suggestion.proposed_category_name,
              "tags": suggestion.tags}
    timings.update({"method": method, "fallback": method == "RULES_FALLBACK",
                    "t_suggest_ms": _ms(started)})
    payload = {"workspaceId": str(job.workspace_id), "versionId": str(job.version_id),
               "method": method, **result, "timings": timings}

    async with tenant_tx(deps.engine, job.workspace_id) as conn:
        # Same transaction as the outbox row: if the lease was lost, nothing below is written.
        if not await suggestions.finish(conn, job, status="DONE", result=result, method=method,
                                        timings=timings):
            bound.warning("suggest_lease_lost")
            return "SUPERSEDED"
        if method == "LLM" and cached is None:
            await suggestions.cache_put(conn, job.workspace_id, key,
                                        {"suggestion": asdict(suggestion)})
        await outbox.add(conn, workspace_id=job.workspace_id, aggregate_id=job.document_id,
                         event_type="SUGGESTIONS_READY", payload=payload)
    bound.info("suggest_done", method=method, **{k: v for k, v in timings.items()
                                                  if k in ("llm_ms", "cache_hit", "attempts")})
    return "DONE"


async def drain(deps: SuggestDeps, lease_seconds: int) -> int:
    """Run due suggestion jobs until none is left; returns how many were handled.

    The caller pushes the outbox afterwards, as it does for ingestion.
    """
    handled = 0
    while True:
        async with system_tx(deps.engine) as conn:
            job = await suggestions.claim(conn, lease_seconds)
        if job is None:
            break
        await handle(job, deps)
        handled += 1
    return handled
