"""V2-10 milestone 3, parts that need no database: step order, titles, SSE framing, config."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from fakes import BowEmbedder, ScriptedChain
from sopilot_ai.api.conversations import with_pings
from sopilot_ai.config import Settings
from sopilot_ai.conversations.events import PING, Event
from sopilot_ai.conversations.service import QAService, make_title
from sopilot_ai.conversations.steps import _pump
from sopilot_ai.providers.llm import LLMError
from sopilot_ai.providers.registry import ModelsConfig, RetrievalConfig
from sopilot_ai.qa.pipeline import STEP_ORDER
from sopilot_ai.quota.counters import QuotaCounter, QuotaState, Reservation
from sopilot_ai.retrieval.context import ContextConfig
from sopilot_ai.retrieval.retriever import Retriever

MODELS = Path(__file__).resolve().parents[2] / "config" / "models.yaml"


def test_the_service_chain_follows_the_documented_step_order() -> None:
    service = QAService(None, Retriever(BowEmbedder(), RetrievalConfig()),  # type: ignore[arg-type]
                        ScriptedChain(), ScriptedChain(), context=ContextConfig(),
                        quota=QuotaCounter(None))  # type: ignore[arg-type]
    assert tuple(s.name for s in service.steps()) == STEP_ORDER


# -- titles come from rules and never carry masked PII ------------------------------------------

def test_title_is_the_question_when_short() -> None:
    assert make_title("  Quy trình   nghỉ phép  ") == "Quy trình nghỉ phép"


def test_title_is_cut_at_a_word_boundary_with_an_ellipsis() -> None:
    title = make_title("quy trình " * 30)
    assert title.endswith("…") and len(title) <= 61 and not title.endswith(" …")
    assert " " not in title[-3:-1] or title[-2] != " "


def test_title_masks_pii_and_has_a_fallback() -> None:
    assert "0912345678" not in make_title("gọi 0912345678 hoặc a@b.vn để hỏi quy trình")
    assert make_title("   ") == "Cuộc hội thoại mới"


# -- SSE framing --------------------------------------------------------------------------------

def test_an_event_is_one_sse_block_with_compact_utf8_json() -> None:
    block = Event("delta", {"text": "Xin chào"}).sse()
    assert block == 'event: delta\ndata: {"text":"Xin chào"}\n\n'
    assert json.loads(block.splitlines()[1].removeprefix("data: ")) == {"text": "Xin chào"}


async def test_a_ping_comment_goes_out_while_the_pipeline_is_quiet() -> None:
    async def slow():  # noqa: ANN202
        yield Event("meta", {})
        await asyncio.sleep(0.08)
        yield Event("done", {})

    out = [chunk async for chunk in with_pings(slow(), interval=0.02)]
    assert out[0].startswith("event: meta") and out[-1].startswith("event: done")
    assert PING in out and out.count(PING) >= 2


async def test_closing_the_stream_early_closes_the_pipeline() -> None:
    closed = asyncio.Event()

    async def source():  # noqa: ANN202
        try:
            yield Event("meta", {})
            await asyncio.sleep(10)
            yield Event("done", {})
        finally:
            closed.set()

    stream = with_pings(source(), interval=1)
    assert (await stream.__anext__()).startswith("event: meta")
    await stream.aclose()
    assert closed.is_set()


# -- quota bookkeeping --------------------------------------------------------------------------

def test_questions_left_is_none_when_the_user_limit_is_off() -> None:
    assert Reservation(QuotaState.OFF).questions_left is None
    assert Reservation(QuotaState.RESERVED, user_used=3, user_limit=0).questions_left is None


def test_questions_left_counts_a_given_back_question() -> None:
    held = Reservation(QuotaState.RESERVED, user_used=2, user_limit=5, user_reserved=True)
    assert held.questions_left == 3
    from dataclasses import replace

    assert replace(held, released=True).questions_left == 4


# -- config -------------------------------------------------------------------------------------

def test_models_yaml_declares_the_context_assembly_settings() -> None:
    cfg = ModelsConfig.load(MODELS).context()
    assert cfg == ContextConfig(expand=True, section_max_tokens=1200, max_tokens=3000)


def test_context_config_falls_back_to_defaults_when_the_section_is_missing() -> None:
    assert ModelsConfig(raw={"retrieval": {}}).context() == ContextConfig()


@pytest.mark.parametrize("raw", ["false", False])
def test_context_expand_can_be_switched_off(raw) -> None:  # noqa: ANN001
    cfg = ModelsConfig(raw={"retrieval": {"context": {"expand": raw}}}).context()
    assert cfg.expand is False


# -- closing the stream while the pipeline is quiet ---------------------------------------------

async def test_closing_during_a_ping_interval_unwinds_the_source_without_an_error() -> None:
    closed = asyncio.Event()

    async def source():  # noqa: ANN202
        try:
            yield Event("meta", {})
            await asyncio.sleep(10)
        finally:
            closed.set()

    stream = with_pings(source(), interval=0.02)
    assert (await stream.__anext__()).startswith("event: meta")
    assert await stream.__anext__() == PING  # the source is now inside a running __anext__
    await stream.aclose()  # used to raise "asynchronous generator is already running"
    await asyncio.sleep(0.05)
    assert closed.is_set()


# -- reading the LLM stream on one thread -------------------------------------------------------

async def test_pump_yields_deltas_in_order_and_closes_the_generator() -> None:
    closed: list[bool] = []

    def gen():  # noqa: ANN202
        try:
            yield from ("a", "b", "c")
        finally:
            closed.append(True)

    assert [d async for d in _pump(gen(), threading.Event())] == ["a", "b", "c"]
    assert closed == [True]


async def test_pump_raises_the_llm_error_of_the_generator() -> None:
    def gen():  # noqa: ANN202
        yield "a"
        raise LLMError("LLM_UNAVAILABLE")

    seen: list[str] = []
    with pytest.raises(LLMError) as err:
        async for d in _pump(gen(), threading.Event()):
            seen.append(d)
    assert seen == ["a"] and err.value.code == "LLM_UNAVAILABLE"


async def test_a_consumer_that_leaves_mid_read_closes_the_stream_on_the_reader_thread() -> None:
    reading, release = threading.Event(), threading.Event()
    state: dict[str, object] = {"produced": []}

    def gen():  # noqa: ANN202
        try:
            reading.set()
            release.wait(5)  # the model is slow: the read is blocked
            for piece in ("one", "two"):
                state["produced"].append(piece)  # type: ignore[union-attr]
                yield piece
        finally:
            state["closed_on"] = threading.current_thread()

    stop = threading.Event()
    task = asyncio.ensure_future(_pump(gen(), stop).__anext__())
    await asyncio.to_thread(reading.wait, 5)
    task.cancel()  # the client left while next() was still running
    stop.set()
    release.set()
    await asyncio.sleep(0.2)
    assert state["closed_on"] is not threading.main_thread()  # no cross-thread close, no ValueError
    assert state["produced"] == ["one"]  # it stopped at the flag instead of reading on


# -- settings -----------------------------------------------------------------------------------

def test_a_blank_followup_limit_means_the_yaml_value_not_a_crash() -> None:
    base = {"SOPILOT_DB_URL": "postgresql://unused", "SOPILOT_INTERNAL_TOKEN": "t"}
    assert Settings.model_validate({**base, "SOPILOT_FOLLOWUP_MAX_TOKENS": ""}
                                   ).followup_max_tokens is None
    assert Settings.model_validate({**base, "SOPILOT_FOLLOWUP_MAX_TOKENS": "4"}
                                   ).followup_max_tokens == 4


def test_a_given_back_question_is_not_given_back_twice() -> None:
    from dataclasses import replace
    from datetime import date
    from uuid import uuid4

    held = Reservation(QuotaState.RESERVED, date(2026, 11, 9), 1, 5, True, False)
    done = replace(held, released=True)
    counter = QuotaCounter(None)  # type: ignore[arg-type]  # a second release never reaches the DB
    assert asyncio.run(counter.release(uuid4(), uuid4(), done)) is done
