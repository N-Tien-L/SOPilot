"""V2-48: one question can turn the reranker off; the chat can ask whether one is configured.

No database and no model: the search functions are replaced by in-memory lists.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import numpy as np
import pytest
import yaml
from fastapi import FastAPI

from fakes import BowEmbedder, FakeEmbedder, ScriptedChain
from sopilot_ai.api import conversations as api
from sopilot_ai.api.conversations import MessageIn
from sopilot_ai.auth.jwt import current_principal
from sopilot_ai.conversations import steps
from sopilot_ai.conversations.service import ConversationRef, QAService
from sopilot_ai.conversations.steps import QAContext, RetrieveStep
from sopilot_ai.conversations.trace import TraceCollector
from sopilot_ai.providers.registry import RetrievalConfig
from sopilot_ai.quota.counters import QuotaCounter
from sopilot_ai.retrieval import search
from sopilot_ai.retrieval.access_filter import Principal
from sopilot_ai.retrieval.context import ContextConfig
from sopilot_ai.retrieval.retriever import RetrievalResult, Retriever

PRINCIPAL = Principal(uuid4(), uuid4(), "ADMIN")
A, B, C = (uuid4() for _ in range(3))
DOC, VERSION = uuid4(), uuid4()


class CountingReranker:
    """Prefers the chunk fusion ranks last, so a reranked order differs from the fusion order."""

    name, model, revision = "local", "fake/reranker", "r1"

    def __init__(self) -> None:
        self.calls = 0

    def score(self, query: str, passages: list[str]) -> np.ndarray:  # noqa: ARG002
        self.calls += 1
        return np.array([0.1 * (i + 1) for i in range(len(passages))], dtype=np.float32)


@pytest.fixture
def corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dense says A, B, C; BM25 says A, C, B; so fusion order is A, then B/C by tie rules."""

    def hit(chunk: UUID, score: float) -> search.Hit:
        return search.Hit(chunk, DOC, VERSION, "vi", score)

    async def dense(*_a: object, **_k: object) -> list[search.Hit]:
        return [hit(A, 0.9), hit(B, 0.6), hit(C, 0.5)]

    async def bm25(*_a: object, **_k: object) -> list[search.Hit]:
        return [hit(A, 5.0), hit(C, 3.0), hit(B, 1.0)]

    async def index_texts(_conn: object, _p: object, ids: list[UUID]) -> dict[UUID, str]:
        return {i: f"text {i}" for i in ids}

    async def cosine_by_id(*_a: object, **_k: object) -> dict[UUID, float]:
        return {}

    monkeypatch.setattr(search, "dense", dense)
    monkeypatch.setattr(search, "bm25", bm25)
    monkeypatch.setattr(search, "index_texts", index_texts)
    monkeypatch.setattr(search, "cosine_by_id", cosine_by_id)


def _retriever(reranker: CountingReranker | None) -> Retriever:
    return Retriever(FakeEmbedder(), RetrievalConfig(), reranker)


async def _retrieve(retriever: Retriever, **kw: object) -> tuple[RetrievalResult, list[tuple]]:
    phases: list[tuple] = []
    result = await retriever.retrieve(
        None, PRINCIPAL, "quy trinh", on_phase=lambda *p: phases.append(p), **kw)  # type: ignore[arg-type]
    return result, phases


def _phase(phases: list[tuple], name: str) -> list[tuple]:
    return [p for p in phases if p[0] == name]


# -- the retriever -----------------------------------------------------------------------------

@pytest.mark.usefixtures("corpus")
async def test_rerank_false_never_calls_the_reranker_and_uses_the_hybrid_gate() -> None:
    reranker = CountingReranker()
    result, phases = await _retrieve(_retriever(reranker), rerank=False)

    assert reranker.calls == 0
    assert result.mode == "hybrid"
    assert result.threshold == 0.45  # the hybrid threshold, not hybrid_rerank (0.30)
    assert result.gate_score == pytest.approx(0.9)  # dense cosine of the best fused chunk
    assert result.stats.rerank_enabled is False and result.stats.rerank_model is None
    assert all(c.rerank_score is None for c in result.candidates)
    assert [c.chunk_id for c in result.candidates] == sorted(
        (c.chunk_id for c in result.candidates),
        key=lambda k: next(c.fusion_score for c in result.candidates if c.chunk_id == k),
        reverse=True)  # fusion order
    assert result.candidates[0].chunk_id == A
    assert result.hits == result.candidates  # passed: the hits follow fusion order
    assert _phase(phases, "retrieve_rerank") == [
        ("retrieve_rerank", "skipped", 0, {"skipped": True, "reason": "rerank_off_by_request"})]


@pytest.mark.usefixtures("corpus")
@pytest.mark.parametrize("flag", [None, True])
async def test_rerank_default_or_true_keeps_the_configured_reranker(flag: bool | None) -> None:
    reranker = CountingReranker()
    kw = {} if flag is None else {"rerank": flag}
    result, phases = await _retrieve(_retriever(reranker), **kw)

    assert reranker.calls == 1
    assert result.mode == "hybrid_rerank"
    assert result.threshold == 0.30
    assert result.stats.rerank_enabled is True and result.stats.rerank_model == "fake/reranker"
    assert result.candidates[0].rerank_score is not None
    assert [p[1] for p in _phase(phases, "retrieve_rerank")] == ["running", "passed"]


@pytest.mark.usefixtures("corpus")
async def test_the_reranker_changes_the_order_that_rerank_false_keeps() -> None:
    with_rerank, _ = await _retrieve(_retriever(CountingReranker()))
    without, _ = await _retrieve(_retriever(CountingReranker()), rerank=False)
    assert [c.chunk_id for c in with_rerank.candidates] != [c.chunk_id for c in without.candidates]


@pytest.mark.usefixtures("corpus")
@pytest.mark.parametrize("flag", [None, True, False])
async def test_without_a_reranker_rerank_is_hybrid_and_never_an_error(flag: bool | None) -> None:
    kw = {} if flag is None else {"rerank": flag}
    result, phases = await _retrieve(_retriever(None), **kw)

    assert result.mode == "hybrid" and result.threshold == 0.45
    assert result.stats.rerank_enabled is False
    assert _phase(phases, "retrieve_rerank") == [
        ("retrieve_rerank", "skipped", 0, {"skipped": True, "reason": "rerank_not_configured"})]


def test_mode_for_follows_the_flag_and_the_configuration() -> None:
    with_rerank, without = _retriever(CountingReranker()), _retriever(None)
    assert [with_rerank.mode_for(f) for f in (None, True, False)] == [
        "hybrid_rerank", "hybrid_rerank", "hybrid"]
    assert [without.mode_for(f) for f in (None, True, False)] == ["hybrid"] * 3
    assert with_rerank.mode == "hybrid_rerank" and without.mode == "hybrid"
    dense_only = Retriever(FakeEmbedder(), RetrievalConfig(mode="dense"))
    assert dense_only.mode_for(False) == "dense"  # nothing to turn off: the mode is unchanged


def test_the_skipped_phase_has_its_own_summary() -> None:
    collector = TraceCollector(message_id=uuid4(), conversation_id=uuid4(), mode="hybrid",
                               lang="vi")
    payload = collector.record_phase("retrieve_rerank", "skipped", 0, {
        "skipped": True, "reason": "rerank_off_by_request"})
    assert payload["status"] == "skipped"
    assert payload["detail"]["reason"] == "rerank_off_by_request"
    assert "turned off" in payload["summary"]
    assert payload["stage"] == "retrieve_rerank"  # the reranker card, not post_checks


@pytest.mark.parametrize("flag", [None, True, False])
async def test_an_empty_pool_is_not_reported_as_reranked(
        monkeypatch: pytest.MonkeyPatch, flag: bool | None) -> None:
    async def nothing(*_a: object, **_k: object) -> list[search.Hit]:
        return []

    monkeypatch.setattr(search, "dense", nothing)
    monkeypatch.setattr(search, "bm25", nothing)
    reranker = CountingReranker()
    kw = {} if flag is None else {"rerank": flag}
    result, phases = await _retrieve(_retriever(reranker), **kw)

    assert reranker.calls == 0 and result.candidates == [] and result.passed is False
    assert result.mode == "hybrid"  # the gate mode that really ran
    assert result.stats.rerank_enabled is False and result.stats.rerank_model is None
    assert _phase(phases, "retrieve_rerank")[-1][1] in ("passed", "skipped")  # never left running


# -- the pipeline and the SSE meta event -------------------------------------------------------

def _service(reranker: CountingReranker | None) -> QAService:
    return QAService(None, Retriever(BowEmbedder(), RetrievalConfig(), reranker),  # type: ignore[arg-type]
                     ScriptedChain(), ScriptedChain(), context=ContextConfig(),
                     quota=QuotaCounter(None))  # type: ignore[arg-type]


async def _meta_mode(service: QAService, **kw: object) -> str:
    stream = service.answer(PRINCIPAL, ConversationRef(uuid4(), True), "Quy trinh nghi phep?",
                            "vi", **kw)  # type: ignore[arg-type]
    try:
        first = await stream.__anext__()
    finally:
        await stream.aclose()
    assert first.name == "meta"
    return first.data["mode"]


async def test_meta_mode_is_the_mode_of_this_question() -> None:
    with_rerank, without = _service(CountingReranker()), _service(None)
    assert await _meta_mode(with_rerank) == "hybrid_rerank"
    assert await _meta_mode(with_rerank, rerank=True) == "hybrid_rerank"
    assert await _meta_mode(with_rerank, rerank=False) == "hybrid"
    assert await _meta_mode(without, rerank=True) == "hybrid"
    assert await _meta_mode(without) == "hybrid"


async def test_the_retrieve_step_hands_the_flag_to_the_retriever(
        monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    class SpyRetriever:
        async def retrieve(self, _conn: object, _p: object, _q: str, **kw: object
                           ) -> RetrievalResult:
            seen.append(kw["rerank"])
            return RetrievalResult("hybrid", [], None, None, True)

    @asynccontextmanager
    async def no_tx(*_a: object, **_k: object):  # noqa: ANN202
        yield None

    async def empty(*_a: object, **_k: object) -> dict | list:
        return []

    monkeypatch.setattr(steps, "tenant_tx", no_tx)
    monkeypatch.setattr(search, "document_titles", lambda *_a, **_k: _async({}))
    monkeypatch.setattr(steps.context_store, "load_chunks", empty)
    for flag in (None, True, False):
        ctx = QAContext(question="q", principal=PRINCIPAL, rerank=flag,
                        frame=SimpleNamespace(lang="vi"))  # type: ignore[arg-type]
        await RetrieveStep(SpyRetriever(), None).run(ctx)  # type: ignore[arg-type]
    assert seen == [None, True, False]


async def _async(value: object) -> object:
    return value


@pytest.mark.parametrize(("body", "expected"), [
    ({"content": "q"}, None),
    ({"content": "q", "rerank": None}, None),
    ({"content": "q", "rerank": True}, True),
    ({"content": "q", "rerank": False}, False),
])
def test_message_in_accepts_rerank_true_false_or_absent(body: dict, expected: bool | None) -> None:
    assert MessageIn.model_validate(body).rerank is expected


async def test_post_message_passes_the_flag_to_the_service() -> None:
    calls: list[dict] = []

    class Service:
        async def open(self, _p: Principal, _cid: UUID | None) -> ConversationRef:
            return ConversationRef(uuid4(), True)

        async def answer(self, _p: Principal, _ref: ConversationRef, _content: str, _lang: object,
                         **kw: object):  # noqa: ANN202
            calls.append(kw)
            yield api.Event("done", {})

    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[current_principal] = lambda: PRINCIPAL
    app.dependency_overrides[api.get_qa_service] = lambda: Service()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://ai") as client:
        for body in ({"content": "q"}, {"content": "q", "rerank": False}):
            resp = await client.post("/ai/v1/conversations/new/messages", json=body)
            assert resp.status_code == 200
    assert [c["rerank"] for c in calls] == [None, False]


# -- GET /ai/v1/retrieval/options --------------------------------------------------------------

def _options_app(tmp_path: Path, rerank: dict | None, *, authenticated: bool = True) -> FastAPI:
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({"rerank": rerank} if rerank is not None else {}),
                    encoding="utf-8")
    app = FastAPI()
    app.include_router(api.router)
    app.state.models_config_path = path

    app.state.factory_calls = []

    async def factory() -> QAService:  # building it loads the embedding model: never for options
        app.state.factory_calls.append(1)
        raise RuntimeError("not available")

    app.state.qa_service_factory = factory
    if authenticated:
        app.dependency_overrides[current_principal] = lambda: PRINCIPAL
    else:
        app.state.token_verifier = SimpleNamespace()  # never reached without a bearer header
    return app


async def _options(app: FastAPI) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://ai") as client:
        return await client.get("/ai/v1/retrieval/options")


@pytest.mark.parametrize(("rerank", "available"), [
    ({"enabled": True, "provider": "modal"}, True),
    ({"enabled": "true", "provider": "local"}, True),
    ({"enabled": False, "provider": "modal"}, False),
    ({"enabled": True, "provider": "none"}, False),
    ({"enabled": True}, False),  # no provider means none
    (None, False),  # no rerank section at all
])
async def test_options_report_whether_a_reranker_is_configured(
        tmp_path: Path, rerank: dict | None, available: bool) -> None:
    app = _options_app(tmp_path, rerank)
    resp = await _options(app)
    assert resp.status_code == 200
    assert resp.json() == {"rerank": {"available": available}}
    assert app.state.factory_calls == []  # the QA service was never built


async def test_options_need_a_signed_in_user(tmp_path: Path) -> None:
    resp = await _options(_options_app(tmp_path, {"enabled": True, "provider": "modal"},
                                       authenticated=False))
    assert resp.status_code == 401
