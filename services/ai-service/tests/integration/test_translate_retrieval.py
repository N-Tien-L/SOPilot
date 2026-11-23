# ruff: noqa: F811 - imported fixtures are used by name as test arguments
"""A question is also asked in the language of the documents (V2-47, TECH-V2-ai-service §6.4b).

The corpus of ``test_retrieval`` has three Vietnamese documents and one English one. A Vietnamese
question about the English document shares no word with it, so BM25 finds nothing and the dense
score is noise; the translated question finds it, and the English chunks are reranked with the
English question.
"""
from __future__ import annotations

import dataclasses

import numpy as np
from test_retrieval import (  # noqa: F401
    Corpus,
    body,
    client,
    corpus,
    deps,
    docs_of,
    embedder,
    ingest,
    keypair,
    run,
    sql,
    store,
)

from fakes import BowEmbedder, ScriptedChain
from sopilot_ai.conversations.steps import QAContext, TranslateStep
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.providers.registry import RetrievalConfig
from sopilot_ai.qa.query_frame import build_query_frame
from sopilot_ai.retrieval import search
from sopilot_ai.retrieval.retriever import AltQuery, Retriever

VI_QUESTION = "thiết bị xách tay cần ai phê chuẩn"  # no word of the English document
EN_QUESTION = "who approves a laptop request"


def _candidate(result, corpus: Corpus, name: str):  # noqa: ANN001, ANN202
    doc = corpus.docs[name][0]
    return next((c for c in result.candidates if c.document_id == doc), None)


async def test_translated_question_reaches_a_chunk_the_original_cannot(engine, corpus) -> None:  # noqa: ANN001
    retriever = Retriever(BowEmbedder(), RetrievalConfig())
    plain = await run(engine, retriever, corpus.principal(), VI_QUESTION, query_lang="vi")
    both = await run(engine, retriever, corpus.principal(), VI_QUESTION, query_lang="vi",
                     alt=AltQuery(EN_QUESTION, "en"))
    laptop_plain = _candidate(plain, corpus, "laptop")
    laptop_both = _candidate(both, corpus, "laptop")
    # no word is shared across the two languages, so BM25 finds nothing for the original
    assert laptop_plain is None or laptop_plain.bm25_score is None
    assert laptop_both is not None and laptop_both.bm25_score is not None
    assert docs_of(both, corpus)[0] == "laptop"


async def test_without_a_translation_the_retrieval_is_unchanged(engine, corpus) -> None:  # noqa: ANN001
    retriever = Retriever(BowEmbedder(), RetrievalConfig())
    one = await run(engine, retriever, corpus.principal(), "quy trình mua hàng", query_lang="vi")
    two = await run(engine, retriever, corpus.principal(), "quy trình mua hàng", query_lang="vi",
                    alt=None)
    assert [c.chunk_id for c in one.candidates] == [c.chunk_id for c in two.candidates]


async def test_each_chunk_is_reranked_with_the_question_in_its_own_language(  # noqa: ANN001
        engine, corpus) -> None:
    class Recording:
        name, model, revision = "local", "fake/rerank", "r"

        def __init__(self) -> None:
            self.calls: list[tuple[str, list[str]]] = []

        def score(self, query: str, passages):  # noqa: ANN001, ANN201
            self.calls.append((query, list(passages)))
            return np.array([0.9 if "laptop" in p.lower() else 0.1 for p in passages],
                            dtype=np.float32)

    rerank = Recording()
    cfg = RetrievalConfig(thresholds={"hybrid": 0.99, "hybrid_rerank": 0.5})
    res = await run(engine, Retriever(BowEmbedder(), cfg, rerank), corpus.principal(),
                    VI_QUESTION, query_lang="vi", alt=AltQuery(EN_QUESTION, "en"))
    by_query = {q: passages for q, passages in rerank.calls}
    assert set(by_query) == {VI_QUESTION, EN_QUESTION}
    assert all("laptop" in p.lower() for p in by_query[EN_QUESTION])  # English chunks only
    assert not any("laptop" in p.lower() for p in by_query[VI_QUESTION])  # Vietnamese chunks only
    assert docs_of(res, corpus)[0] == "laptop" and res.passed


async def test_one_rerank_call_when_there_is_no_translation(engine, corpus) -> None:  # noqa: ANN001
    class Counting:
        name, model, revision = "local", "fake/rerank", "r"

        def __init__(self) -> None:
            self.calls = 0

        def score(self, query: str, passages):  # noqa: ANN001, ANN201
            self.calls += 1
            return np.full(len(passages), 0.5, dtype=np.float32)

    rerank = Counting()
    await run(engine, Retriever(BowEmbedder(), RetrievalConfig(), rerank), corpus.principal(),
              "quy trình mua hàng", query_lang="vi")
    assert rerank.calls == 1


async def test_document_languages_count_only_what_the_asker_can_read(engine, corpus) -> None:  # noqa: ANN001
    async def langs(principal):  # noqa: ANN001, ANN202
        async with tenant_tx(engine, principal.workspace_id, principal.user_id) as conn:
            return await search.document_languages(conn, principal)

    assert await langs(corpus.principal("OWNER")) == {"vi": 3, "en": 1}
    assert await langs(corpus.principal("MEMBER")) == {"vi": 2, "en": 1}  # not the department doc


def _ctx(corpus: Corpus, text: str, lang: str, principal=None) -> QAContext:  # noqa: ANN001
    ctx = QAContext(question=text, principal=principal or corpus.principal(), lang=lang)
    ctx.text = ctx.working_text = text
    ctx.frame = build_query_frame(text, lang=lang, known_terms=set(), followup_max_tokens=None)
    return ctx


async def test_step_translates_toward_the_language_of_the_documents(engine, corpus) -> None:  # noqa: ANN001
    chain = ScriptedChain(rewrite=EN_QUESTION)
    ctx = _ctx(corpus, VI_QUESTION, "vi")
    decision = await TranslateStep(chain, engine, 0.2).run(ctx)
    assert not decision.stops
    assert ctx.alt_query == AltQuery(EN_QUESTION, "en")
    assert ctx.route_info["translate"] == {"to": "en", "status": "OK"}
    assert ctx.llm_calls == 1 and len(chain.calls) == 1
    system = chain.calls[0]["messages"][0]["content"]
    assert "English" in system and chain.calls[0]["messages"][1]["content"] == VI_QUESTION


async def test_step_translates_an_english_question_for_a_mostly_vietnamese_workspace(
        engine, corpus) -> None:  # noqa: ANN001
    chain = ScriptedChain(rewrite="ai phê duyệt yêu cầu laptop")
    ctx = _ctx(corpus, EN_QUESTION, "en")
    await TranslateStep(chain, engine, 0.2).run(ctx)
    assert ctx.alt_query == AltQuery("ai phê duyệt yêu cầu laptop", "vi")


async def test_step_does_nothing_below_the_share_or_when_off(engine, corpus) -> None:  # noqa: ANN001
    for share in (0.5, None):  # English is 1 of 4 documents; None = switched off
        chain = ScriptedChain(rewrite=EN_QUESTION)
        ctx = _ctx(corpus, VI_QUESTION, "vi")
        await TranslateStep(chain, engine, share).run(ctx)
        assert ctx.alt_query is None and chain.calls == [] and ctx.llm_calls == 0
        assert "translate" not in ctx.route_info


async def test_step_keeps_the_original_question_when_the_model_fails(engine, corpus) -> None:  # noqa: ANN001
    ctx = _ctx(corpus, VI_QUESTION, "vi")
    decision = await TranslateStep(ScriptedChain(fail=True), engine, 0.2).run(ctx)
    assert not decision.stops and ctx.alt_query is None
    assert ctx.route_info["translate"] == {"to": "en", "status": "FAILED"}


async def test_step_ignores_an_answer_that_is_the_question_itself(engine, corpus) -> None:  # noqa: ANN001
    ctx = _ctx(corpus, VI_QUESTION, "vi")
    await TranslateStep(ScriptedChain(rewrite=VI_QUESTION), engine, 0.2).run(ctx)
    assert ctx.alt_query is None and ctx.route_info["translate"]["status"] == "FAILED"


async def test_step_is_skipped_for_a_language_outside_vi_and_en(engine, corpus) -> None:  # noqa: ANN001
    chain = ScriptedChain(rewrite=EN_QUESTION)
    ctx = _ctx(corpus, VI_QUESTION, "vi")
    assert ctx.frame is not None
    ctx.frame = dataclasses.replace(ctx.frame, lang="fr")  # type: ignore[arg-type]
    await TranslateStep(chain, engine, 0.2).run(ctx)
    assert chain.calls == [] and ctx.alt_query is None


# -- end to end through the QA API -----------------------------------------------------------------

async def test_vietnamese_question_is_answered_from_the_english_document(  # noqa: ANN001
        engine, keypair, corpus, database) -> None:
    from test_qa_api import Harness, data

    h = Harness(engine, keypair, corpus)
    h.rewrite = ScriptedChain(rewrite=EN_QUESTION)
    h.generate = ScriptedChain(("Cần quản lý duyệt [1]. ",))
    h.build(translate=0.2)
    try:
        status, events = await h.ask(corpus.principal(), VI_QUESTION, lang="vi")
        assert status == 200
        assert data(events, "done")["outcome"] == "ANSWERED"
        assert data(events, "citations")[0]["documentId"] == str(corpus.docs["laptop"][0])
        assert len(h.rewrite.calls) == 1  # the translation, not a follow-up rewrite
        assert "English" in h.rewrite.calls[0]["messages"][0]["content"]
        # the answer prompt still carries the question the user asked, in their language
        assert h.generate.calls[0]["messages"][1]["content"] == f"Câu hỏi: {VI_QUESTION}"
        conv = data(events, "meta")["conversationId"]
        route = sql(database, "SELECT route FROM rag.messages WHERE conversation_id = %s "
                              "AND role = 'ASSISTANT'", conv)[0][0]
        assert route["translate"] == {"to": "en", "status": "OK"}
        assert route["llmCalls"] == 2 and "translate" in route["steps"]
        assert route["steps"].index("translate") == route["steps"].index("rewrite") + 1
    finally:
        assert h.client is not None
        await h.client.aclose()
