# ruff: noqa: F811 - imported fixtures are used by name as test arguments
"""Metadata suggestions end to end on Postgres (V2-25, TECH-V2-ai-service §5.7).

Ingest a document with a suggest spec, let the ingest worker make it READY, then run the suggestion
worker with a scripted model. Checks: a suggestion job exists only for a READY version; the
job never reads the stored file; the outbox carries SUGGESTIONS_READY; a model failure falls back
to the rules; the cache answers repeat content in the same workspace only.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from test_retrieval import (  # noqa: F401
    body,
    client,
    deps,
    embedder,
    ingest,
    keypair,
    sql,
    store,
)

from sopilot_ai.db.engine import system_tx, tenant_tx
from sopilot_ai.db.repositories import suggestions
from sopilot_ai.providers.llm import LLMError
from sopilot_ai.suggest import runner
from sopilot_ai.worker import drain as ingest_drain

SOP = """# Quy trình mua hàng

## 1. Mục đích

Quy định cách đặt mua hàng cho các phòng ban trong công ty và cách kiểm tra hàng nhận về.
"""
CAT_ID = str(uuid4())


@pytest.fixture(autouse=True)
def empty_suggestion_queue(database) -> None:  # noqa: ANN001
    """The database is shared by the session: leftover QUEUED jobs must not run in this test."""
    sql(database, "UPDATE rag.suggestion_jobs SET status = 'FAILED' "
        "WHERE status IN ('QUEUED', 'RUNNING')")


class ScriptedChain:
    """Stands in for LLMChain: returns scripted outputs (or raises) and counts calls."""

    def __init__(self, *outputs: Any) -> None:
        self.outputs = list(outputs)
        self.calls = 0

    def complete(self, messages, *, tokens, temperature=None, on_start=None) -> str:  # noqa: ANN001, ARG002
        self.calls += 1
        out = self.outputs.pop(0) if self.outputs else self.outputs_default()
        if isinstance(out, Exception):
            raise out
        return out

    @staticmethod
    def outputs_default() -> str:
        return json.dumps({"description": "default"})


GOOD = json.dumps({"description": "Quy trình mua hàng nội bộ.", "category_id": CAT_ID,
                   "proposed_category_name": None, "tags": ["mua sắm"]})


async def make_ready(client, store, deps, ws: UUID, text_: str = SOP,  # noqa: ANN001
                     categories: list[dict] | None = None) -> tuple[UUID, UUID]:
    doc, ver = uuid4(), uuid4()
    b = body(ws, doc, ver, "procurement.md")
    b["suggest"] = {"enabled": True,
                    "categories": categories if categories is not None
                    else [{"id": CAT_ID, "name": "Mua sắm"}],
                    "tags": ["quy trình"]}
    await ingest(client, store, b, text_)
    assert await ingest_drain(deps, 600, None) == 1
    return doc, ver


def suggest_deps(engine, chain) -> runner.SuggestDeps:  # noqa: ANN001
    return runner.SuggestDeps(engine, chain, "fake-model", model_attempts=2)


def outbox_payload(database, doc: UUID) -> dict:  # noqa: ANN001
    rows = sql(database, "SELECT payload FROM rag.outbox_events "
               "WHERE event_type = 'SUGGESTIONS_READY' AND aggregate_id = %s", doc)
    assert len(rows) == 1, rows
    return rows[0][0]


async def run_suggestions(engine, chain) -> int:  # noqa: ANN001
    return await runner.drain(suggest_deps(engine, chain), 300)


async def test_suggestion_job_exists_only_once_the_version_is_ready(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    doc, ver = await make_ready(client, store, deps, ws)
    rows = sql(database, "SELECT status FROM rag.suggestion_jobs WHERE version_id = %s", ver)
    assert rows == [("QUEUED",)]


async def test_no_suggest_spec_means_no_job(client, store, deps, database) -> None:  # noqa: ANN001
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    await ingest(client, store, body(ws, doc, ver, "x.md"), SOP)  # no "suggest" key
    await ingest_drain(deps, 600, None)
    count = sql(database, "SELECT count(*) FROM rag.suggestion_jobs WHERE version_id = %s", ver)
    assert count == [(0,)]


async def test_job_runs_without_the_stored_file(client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    doc, ver = await make_ready(client, store, deps, ws)
    store.objects.clear()  # the object is gone: the suggestion must not need it
    chain = ScriptedChain(GOOD)
    assert await run_suggestions(engine, chain) == 1
    assert chain.calls == 1
    assert outbox_payload(database, doc)["method"] == "LLM"


async def test_model_result_goes_to_the_outbox_and_is_validated(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    doc, ver = await make_ready(client, store, deps, ws)
    await run_suggestions(engine, ScriptedChain(GOOD))
    payload = outbox_payload(database, doc)
    assert payload["versionId"] == str(ver)
    assert payload["title"] == "Quy trình mua hàng"  # the heading, from the rules
    assert payload["description"] == "Quy trình mua hàng nội bộ."
    assert payload["categoryId"] == CAT_ID
    assert payload["tags"] == ["mua sắm"]
    status = sql(database, "SELECT status, method FROM rag.suggestion_jobs "
                 "WHERE version_id = %s", ver)
    assert status == [("DONE", "LLM")]


async def test_category_outside_the_workspace_list_is_dropped(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    doc, _ = await make_ready(client, store, deps, ws)
    made_up = json.dumps({"description": "d", "category_id": str(uuid4()),
                          "proposed_category_name": "Pháp chế", "tags": []})
    await run_suggestions(engine, ScriptedChain(made_up))
    payload = outbox_payload(database, doc)
    assert payload["categoryId"] is None and payload["proposedCategoryName"] == "Pháp chế"


async def test_model_failure_retries_once_then_falls_back_to_rules(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    doc, ver = await make_ready(client, store, deps, ws)
    chain = ScriptedChain(LLMError("LLM_UNAVAILABLE"), "not json at all")
    await run_suggestions(engine, chain)
    assert chain.calls == 2  # one retry, no more
    payload = outbox_payload(database, doc)
    assert payload["method"] == "RULES_FALLBACK"
    assert payload["title"] == "Quy trình mua hàng" and payload["description"] is None
    assert sql(database, "SELECT status, method FROM rag.suggestion_jobs WHERE version_id = %s",
               ver) == [("DONE", "RULES_FALLBACK")]
    assert sql(database, "SELECT count(*) FROM rag.suggestion_cache WHERE workspace_id = %s",
               ws) == [(0,)]  # fallbacks are never cached


async def test_no_model_configured_means_rules_only(client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    doc, _ = await make_ready(client, store, deps, ws)
    await run_suggestions(engine, None)
    assert outbox_payload(database, doc)["method"] == "RULES_FALLBACK"


async def test_repeat_content_in_the_same_workspace_is_a_cache_hit(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    await make_ready(client, store, deps, ws)
    first = ScriptedChain(GOOD)
    await run_suggestions(engine, first)
    doc2, _ = await make_ready(client, store, deps, ws)  # same bytes, new document
    second = ScriptedChain(GOOD)
    await run_suggestions(engine, second)
    assert first.calls == 1 and second.calls == 0
    payload = outbox_payload(database, doc2)
    assert payload["method"] == "LLM" and payload["timings"]["cache_hit"] is True


async def test_cache_is_never_shared_across_workspaces(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws_a, ws_b = uuid4(), uuid4()
    await make_ready(client, store, deps, ws_a, categories=[{"id": CAT_ID, "name": "Mua sắm"}])
    await run_suggestions(engine, ScriptedChain(GOOD))
    same_list = [{"id": CAT_ID, "name": "Mua sắm"}]
    doc_b, _ = await make_ready(client, store, deps, ws_b, categories=same_list)
    chain_b = ScriptedChain(json.dumps({"description": "B", "tags": []}))
    await run_suggestions(engine, chain_b)
    assert chain_b.calls == 1  # workspace B paid for its own call
    assert outbox_payload(database, doc_b)["description"] == "B"


async def test_claim_respects_rls_and_runs_one_job_at_a_time(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    await make_ready(client, store, deps, ws)
    async with system_tx(engine) as conn:
        job = await suggestions.claim(conn, 300)
    assert job is not None and job.workspace_id == ws
    async with system_tx(engine) as conn:
        assert await suggestions.claim(conn, 300) is None  # the only job is leased now
    running = sql(database, "SELECT status FROM rag.suggestion_jobs WHERE id = %s", job.id)
    assert running == [("RUNNING",)]
    async with tenant_tx(engine, ws) as conn:
        assert await suggestions.extracted_text(conn, ws, job.version_id) is not None


async def test_stale_worker_cannot_finish_or_emit_after_its_lease_was_reclaimed(
        client, store, deps, engine, database) -> None:  # noqa: ANN001
    ws = uuid4()
    doc, _ = await make_ready(client, store, deps, ws)
    async with system_tx(engine) as conn:
        stale = await suggestions.claim(conn, 300)
    assert stale is not None and stale.attempts == 1
    sql(database, "UPDATE rag.suggestion_jobs SET lease_until = now() - interval '1 second' "
        "WHERE id = %s", stale.id)  # the slow worker's lease runs out
    async with system_tx(engine) as conn:
        fresh = await suggestions.claim(conn, 300)
    assert fresh is not None and fresh.id == stale.id and fresh.attempts == 2

    assert await runner.handle(stale, suggest_deps(engine, ScriptedChain(GOOD))) == "SUPERSEDED"
    assert sql(database, "SELECT count(*) FROM rag.outbox_events "
               "WHERE event_type = 'SUGGESTIONS_READY' AND aggregate_id = %s", doc) == [(0,)]
    assert sql(database, "SELECT status FROM rag.suggestion_jobs WHERE id = %s",
               stale.id) == [("RUNNING",)]

    assert await runner.handle(fresh, suggest_deps(engine, ScriptedChain(GOOD))) == "DONE"
    # exactly one event, emitted by the fresh claim
    assert outbox_payload(database, doc)["method"] == "LLM"
