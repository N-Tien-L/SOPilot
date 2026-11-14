# ruff: noqa: F811 - imported fixtures are used by name as test arguments
"""V2-27 semantic router inside the answer pipeline, on real Postgres (TECH-V2-ai-service §7.1).

The layer is the real ``SemanticLayer`` over a table embedder: listed texts get a fixed basis
vector (so the test decides the intent), any other text gets the retriever's own bag-of-words
vector (so a reused vector retrieves exactly what a fresh one would). Thresholds are the
production defaults. The LLM is scripted, as in ``test_qa_api.py``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from uuid import UUID

import numpy as np
import pytest
from test_qa_api import QUESTION, Harness, data, names
from test_retrieval import Corpus, client, corpus, deps, embedder, keypair, sql, store  # noqa: F401

from fakes import BowEmbedder, FakeEmbedder
from sopilot_ai.conversations.factory import build_router, exemplar_hash
from sopilot_ai.qa import router, templates

DIM = BowEmbedder.dim
BASIS = {intent: 1000 + i for i, intent in enumerate(
    ("sop_question", "greeting", "abuse_only", "off_topic", "action_request", "about_source"))}

Q_GREET = "trưởng phòng duyệt đề nghị hôm nay khỏe không"
Q_ABUSE = "trưởng phòng duyệt đề nghị chậm như rùa"
Q_OFF = "trưởng phòng duyệt đề nghị mua vé xem bóng đá"
Q_ACT = "duyệt giúp đề nghị mua hàng trong bao lâu"
Q_SRC = "đề nghị mua hàng đó lấy từ tài liệu nào"
INTENT_OF = {Q_GREET: "greeting", Q_ABUSE: "abuse_only", Q_OFF: "off_topic",
             Q_ACT: "action_request", Q_SRC: "about_source"}
EXEMPLARS = {intent: (f"exemplar of {intent}",) for intent in BASIS}


def basis(intent: str) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[BASIS[intent]] = 1.0
    return v


class TableEmbedder(BowEmbedder):
    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        rows = []
        for t in texts:
            intent = INTENT_OF.get(t) or (t.removeprefix("exemplar of ")
                                         if t.startswith("exemplar of ") else None)
            rows.append(basis(intent) if intent else super().embed([t], is_query=is_query)[0])
        return np.stack(rows)


def layer() -> router.SemanticLayer:
    return router.SemanticLayer(TableEmbedder(), model_id="table@r1", exemplars=EXEMPLARS,
                                thresholds=router.load_thresholds())


@pytest.fixture
async def harness(engine, keypair, corpus: Corpus) -> AsyncIterator[Harness]:  # noqa: ANN001
    h = Harness(engine, keypair, corpus)
    h.build()
    assert h.service is not None
    h.service.semantic = layer()
    yield h
    assert h.client is not None
    await h.client.aclose()


def rebuild(h: Harness, **kw) -> None:  # noqa: ANN003
    h.build(**kw)
    assert h.service is not None
    h.service.semantic = layer()


def row(database, events, cols: str):  # noqa: ANN001, ANN201
    return sql(database, f"SELECT {cols} FROM rag.messages WHERE id = %s",  # noqa: S608
               UUID(data(events, "meta")["messageId"]))[0]


async def test_a_template_intent_answers_with_a_sentence_and_no_llm(
        harness: Harness, database, corpus: Corpus) -> None:  # noqa: ANN001
    _, events = await harness.ask(corpus.principal(), Q_GREET, lang="vi")
    assert names(events) == ["meta", "delta", "done"]
    done = data(events, "done")
    assert done["outcome"] == "TEMPLATE" and done["refusalReason"] is None
    assert done["finalText"] == templates.render("greeting", "vi")
    assert harness.generate.calls == [] and harness.rewrite.calls == []
    route = row(database, events, "route")[0]
    assert route["layer"] == "semantic" and route["intent"] == "greeting"
    assert route["semantic"]["intent"] == "greeting" and route["semantic"]["score"] == 1.0
    assert route["decided_by"] == "semantic_router"


async def test_router_abuse_is_logged_as_an_input_flag(
        harness: Harness, database, corpus: Corpus) -> None:  # noqa: ANN001
    _, events = await harness.ask(corpus.principal(), Q_ABUSE, lang="vi")
    assert data(events, "done")["outcome"] == "TEMPLATE"
    rules = sql(database, "SELECT layer, rule_id FROM rag.guard_events WHERE message_id = %s",
                UUID(data(events, "meta")["messageId"]))
    assert ("INPUT_FLAG", "router.abuse") in rules


async def test_off_topic_is_out_of_scope_only_after_the_gate_refused(
        harness: Harness, database, corpus: Corpus) -> None:  # noqa: ANN001
    rebuild(harness, thresholds={"hybrid": 1.01})
    _, events = await harness.ask(corpus.principal(), Q_OFF, lang="vi")
    refusal, done = data(events, "refusal"), data(events, "done")
    assert refusal["reason"] == "OUT_OF_SCOPE" and "nearestDocuments" not in refusal
    assert refusal["text"] == templates.render("no_evidence", "vi")
    assert (done["outcome"], done["refusalReason"]) == ("REFUSED_NO_EVIDENCE", "OUT_OF_SCOPE")
    stored = row(database, events, "refusal_reason, route")
    assert stored[0] == "OUT_OF_SCOPE" and stored[1]["refusal"] == "OUT_OF_SCOPE"
    assert harness.generate.calls == []


async def test_the_router_never_turns_a_gate_pass_into_a_refusal(
        harness: Harness, corpus: Corpus) -> None:
    _, events = await harness.ask(corpus.principal(), Q_OFF, lang="vi")
    assert data(events, "done")["outcome"] == "ANSWERED"


async def test_a_disclaimer_intent_still_answers_and_adds_the_sentence_before_citations(
        harness: Harness, database, corpus: Corpus) -> None:  # noqa: ANN001
    _, events = await harness.ask(corpus.principal(), Q_ACT, lang="vi")
    done = data(events, "done")
    note = templates.render("disclaimer_action_request", "vi")
    assert done["outcome"] == "ANSWERED" and done["finalText"].endswith(note)
    order = names(events)
    last_delta = len(order) - 1 - order[::-1].index("delta")
    assert data(events, "citations") and last_delta < order.index("citations")
    assert [c["kind"] for c in harness.generate.calls] == ["stream"]
    content, checks = row(database, events, "content, checks")
    assert content.endswith(note) and checks["disclaimers"] == ["action_request"]


async def test_about_source_lists_the_previous_answers_citations_without_llm(
        harness: Harness, corpus: Corpus) -> None:
    owner = corpus.principal()
    _, first = await harness.ask(owner, QUESTION, lang="vi")
    assert data(first, "done")["outcome"] == "ANSWERED"
    calls = len(harness.generate.calls)
    _, second = await harness.ask(owner, Q_SRC, data(first, "meta")["conversationId"], lang="vi")
    done = data(second, "done")
    assert done["outcome"] == "TEMPLATE" and "Quy trình mua hàng" in done["finalText"]
    assert len(harness.generate.calls) == calls and harness.rewrite.calls == []


async def test_about_source_is_not_eligible_without_history(
        harness: Harness, corpus: Corpus) -> None:
    _, events = await harness.ask(corpus.principal(), Q_SRC, lang="vi")
    assert data(events, "done")["outcome"] != "TEMPLATE"


async def test_without_history_the_router_vector_is_reused_for_dense_retrieval(
        harness: Harness, database, corpus: Corpus) -> None:  # noqa: ANN001
    assert harness.service is not None
    retriever_embedder = harness.service.retriever.embedder
    before = list(retriever_embedder.embedded)
    _, events = await harness.ask(corpus.principal(), QUESTION, lang="vi")
    assert data(events, "done")["outcome"] == "ANSWERED"
    assert retriever_embedder.embedded == before  # the query was not embedded a second time
    route = row(database, events, "route")[0]
    assert route["semantic"]["intent"] is None and "semantic_router" in route["steps"]


async def test_exemplar_vectors_are_cached_per_model_in_the_embedding_cache(
        engine, database) -> None:  # noqa: ANN001
    first = FakeEmbedder()
    await build_router(engine, first)
    texts = [t for ts in router.load_exemplars().values() for t in ts]
    assert sorted(first.embedded) == sorted(set(texts))
    count = sql(database, "SELECT count(*) FROM rag.embedding_cache WHERE model = %s AND "
                          "revision = %s AND content_sha256 = %s",
                first.model, first.revision, exemplar_hash(texts[0]))[0][0]
    assert count == 1

    again = FakeEmbedder()
    await build_router(engine, again)
    assert again.embedded == []  # every exemplar came from the cache

    other = FakeEmbedder()
    other.revision = "other-rev"
    await build_router(engine, other)
    assert sorted(other.embedded) == sorted(set(texts))  # a new revision embeds them again
