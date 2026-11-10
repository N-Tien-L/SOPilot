# ruff: noqa: F811 - imported fixtures are used by name as test arguments
"""FR-29 in ai-service: one workspace, documents limited to departments (ADR-007 §4.4-§4.5).

Independent of FR-19 (``test_qa_isolation.py``): there the boundary is the workspace, here it is a
department *inside* one workspace. Three documents, each with its own title and a secret string in
its body: ``WS`` (WORKSPACE), ``A`` (DEPARTMENTS [A]) and ``AB`` (DEPARTMENTS [A, B]). For every
person the test computes what they may read from the ADR-007 matrix and then looks, channel by
channel, for the secret **and** the title of every document they may not read: the dense and BM25
branches, hybrid fusion, what the reranker is handed, the sources in the LLM prompt, the streamed
answer, the citations, the stored turn, the content endpoint, the "nearest documents" of a
refusal and the SQL that widens a hit into its section.

The scripted LLM copies every source it is given, so if any layer let a forbidden chunk through,
its secret would appear in the prompt, the stream or the stored conversation.

The core-api half is ``DepartmentAuthorizationIT``; the two suites do not run together (V2-14).
Not applicable here: a SUSPENDED member. ai-service only verifies the access token, so a member
suspended in core-api keeps reading until the token expires; that window is asserted in core-api.
"""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx
import numpy as np
import pytest
from test_qa_api import data, names, parse_sse
from test_retrieval import (  # noqa: F401
    IDENTITY,
    TOKEN,
    FakeStore,
    bearer,
    body,
    ingest,
    internal,
    keypair,
    sql,
)

from fakes import BowEmbedder, ScriptedChain, Words
from sopilot_ai.api.app import create_app
from sopilot_ai.auth.jwt import TokenVerifier
from sopilot_ai.config import Settings
from sopilot_ai.conversations.service import QAService
from sopilot_ai.conversations.steps import BuildContextStep, QAContext
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.docproc import ChunkConfig
from sopilot_ai.ingest.handler import IngestDeps
from sopilot_ai.providers.registry import RetrievalConfig
from sopilot_ai.qa.pipeline import DecisionKind
from sopilot_ai.quota.counters import QuotaCounter
from sopilot_ai.retrieval import context_store, search
from sopilot_ai.retrieval.access_filter import Principal
from sopilot_ai.retrieval.context import ContextConfig
from sopilot_ai.retrieval.lexical import tokenize
from sopilot_ai.retrieval.retriever import Candidate, RetrievalResult, Retriever
from sopilot_ai.worker import drain

WHO = ("OWNER", "ADMIN", "MEMBER_A", "MEMBER_B", "MEMBER_NO_DEPT")
DOCS = ("WS", "A", "AB")
QUESTION = "mật khẩu kho dữ liệu là gì"
FOLLOWUP = "còn mật khẩu kho dữ liệu thì sao"
SECRETS = {"WS": "SECRET_WS_5521", "A": "SECRET_A_8834", "AB": "SECRET_AB_1907"}
TITLES = {"WS": "Quy trình WS-5521", "A": "Quy trình A-8834", "AB": "Quy trình AB-1907"}
_SOURCES = re.compile(r'<source n="(\d+)"[^>]*>\n(.*?)\n</source>', re.DOTALL)


def can_read(who: str, doc: str) -> bool:
    """ADR-007 §4.4, the three read rows: A is the department of MEMBER_A, B of MEMBER_B."""
    if who in ("OWNER", "ADMIN"):
        return True
    if who == "MEMBER_A":
        return True
    if who == "MEMBER_B":
        return doc != "A"
    return doc == "WS"


def readable(who: str) -> set[str]:
    return {d for d in DOCS if can_read(who, d)}


def doc_text(doc: str) -> str:
    return (f"# {TITLES[doc]}\n\n## 1. Truy cập\n\nMật khẩu kho dữ liệu của {TITLES[doc]} là "
            f"{SECRETS[doc]} và chỉ người có quyền mới được biết mật khẩu này.\n")


def echo_all_sources(messages) -> list[str]:  # noqa: ANN001
    """What a model that copies its whole context would write, citing every source."""
    found = _SOURCES.findall(messages[0]["content"])
    text = "\n".join(t for _, t in found) or "Không có nguồn"
    return [text + " " + " ".join(f"[{n}]" for n, _ in found)]


# -- the world -----------------------------------------------------------------------------------

@dataclass
class Doc:
    id: UUID
    ver: UUID
    name: str


@dataclass
class World:
    engine: object
    keypair: object
    database: object
    ws: UUID
    dept_a: UUID
    dept_b: UUID
    docs: dict[str, Doc]
    principals: dict[str, Principal]
    client: httpx.AsyncClient
    store: FakeStore
    deps: IngestDeps

    def name_of(self, document_id: UUID) -> str:
        return next(d.name for d in self.docs.values() if d.id == document_id)

    def names_of(self, ids) -> set[str]:  # noqa: ANN001
        return {self.name_of(i) for i in ids}


def _app(engine, keypair, **kw) -> httpx.AsyncClient:  # noqa: ANN001, ANN003
    settings = Settings.model_validate({"SOPILOT_DB_URL": "postgresql://unused",
                                        "SOPILOT_INTERNAL_TOKEN": TOKEN})
    app = create_app(settings, engine, embedding_identity=IDENTITY,
                     token_verifier=TokenVerifier(key_for=lambda _t: keypair[1]), **kw)
    app.state.engine = engine  # ASGITransport does not run the lifespan
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ai")


async def build_world(engine, keypair, database) -> World:  # noqa: ANN001
    store, embedder = FakeStore(), BowEmbedder()
    deps = IngestDeps(engine=engine, store=store, embedder=embedder, tokenizer=Words(),
                      chunk_config=ChunkConfig(), max_attempts=3, backoff_base_seconds=0)
    client = _app(engine, keypair)
    ws, dept_a, dept_b = uuid4(), uuid4(), uuid4()
    scope = {"WS": ("WORKSPACE", None), "A": ("DEPARTMENTS", [dept_a]),
             "AB": ("DEPARTMENTS", [dept_a, dept_b])}
    docs: dict[str, Doc] = {}
    for name in DOCS:
        doc, ver = uuid4(), uuid4()
        visibility, departments = scope[name]
        await ingest(client, store, body(ws, doc, ver, TITLES[name], visibility=visibility,
                                         departments=departments), doc_text(name))
        docs[name] = Doc(doc, ver, name)
    assert await drain(deps, 600, None) == len(DOCS)
    principals = {
        "OWNER": Principal(uuid4(), ws, "OWNER"), "ADMIN": Principal(uuid4(), ws, "ADMIN"),
        "MEMBER_A": Principal(uuid4(), ws, "MEMBER", dept_a),
        "MEMBER_B": Principal(uuid4(), ws, "MEMBER", dept_b),
        "MEMBER_NO_DEPT": Principal(uuid4(), ws, "MEMBER")}
    return World(engine, keypair, database, ws, dept_a, dept_b, docs, principals, client, store,
                 deps)


@pytest.fixture(scope="module")
async def shared(engine, keypair, database) -> AsyncIterator[World]:  # noqa: ANN001
    """One world for every read-only test: nothing here changes the access of a document."""
    w = await build_world(engine, keypair, database)
    yield w
    await w.client.aclose()


@pytest.fixture
async def fresh(engine, keypair, database) -> AsyncIterator[World]:  # noqa: ANN001
    """A private world for a test that changes access, deletes or adds documents."""
    w = await build_world(engine, keypair, database)
    yield w
    await w.client.aclose()


# -- channels ------------------------------------------------------------------------------------

async def dense_docs(w: World, p: Principal, *, pool: int = 50) -> set[str]:
    qvec = BowEmbedder().embed([QUESTION], is_query=True)[0]
    async with tenant_tx(w.engine, p.workspace_id, p.user_id) as conn:
        hits = await search.dense(conn, p, qvec, model=IDENTITY[0], revision=IDENTITY[1],
                                  pool=pool)
    return w.names_of(h.document_id for h in hits)


async def bm25_docs(w: World, p: Principal, *, pool: int = 50) -> set[str]:
    async with tenant_tx(w.engine, p.workspace_id, p.user_id) as conn:
        hits = await search.bm25(conn, p, tokenize(QUESTION, role="query"), pool=pool)
    return w.names_of(h.document_id for h in hits)


def hybrid_retriever(**cfg) -> Retriever:  # noqa: ANN003
    return Retriever(BowEmbedder(), RetrievalConfig(thresholds={"hybrid": 0.0}, **cfg))


async def hybrid_docs(w: World, p: Principal) -> set[str]:
    async with tenant_tx(w.engine, p.workspace_id, p.user_id) as conn:
        res = await hybrid_retriever().retrieve(conn, p, QUESTION)
    return w.names_of(c.document_id for c in res.candidates)


async def content_status(w: World, p: Principal, doc: Doc) -> httpx.Response:
    return await w.client.get(f"/ai/v1/documents/{doc.id}/versions/{doc.ver}/content",
                              headers=bearer(w.keypair, p))


class Qa:
    """The question-answering API over a world, with the LLM chains it was built with."""

    def __init__(self, client: httpx.AsyncClient, w: World, generate: ScriptedChain,
                 rewrite: ScriptedChain) -> None:
        self.client, self.w, self.generate, self.rewrite = client, w, generate, rewrite

    async def ask(self, p: Principal, content: str = QUESTION, conversation: str = "new"):  # noqa: ANN201
        resp = await self.client.post(
            f"/ai/v1/conversations/{conversation}/messages", json={"content": content},
            headers=bearer(self.w.keypair, p))
        assert resp.status_code == 200, resp.text
        return resp.text, parse_sse(resp.text)

    async def conversation(self, p: Principal, conversation_id: str) -> httpx.Response:
        return await self.client.get(f"/ai/v1/conversations/{conversation_id}",
                                     headers=bearer(self.w.keypair, p))

    def prompt(self) -> str:
        """Everything the answering model was given on its last call."""
        streams = [c for c in self.generate.calls if c["kind"] == "stream"]
        if not streams:
            return ""
        last = streams[-1]
        return "\n".join(m["content"] for m in last["messages"])


@asynccontextmanager
async def qa(w: World, *, thresholds: dict | None = None,
             rewrite: str = "") -> AsyncIterator[Qa]:
    generate, rewriter = ScriptedChain(echo_all_sources), ScriptedChain(rewrite=rewrite)
    retrieval = RetrievalConfig(thresholds=thresholds or {"hybrid": 0.0})
    service = QAService(w.engine, Retriever(BowEmbedder(), retrieval), generate, rewriter,
                        context=ContextConfig(), quota=QuotaCounter(w.engine))
    async with _app(w.engine, w.keypair, qa_service=service) as client:
        yield Qa(client, w, generate, rewriter)


def assert_no_trace(text: str, forbidden: set[str], w: World, cell: str) -> None:
    """Neither the secret, the title nor the id of a document the asker may not read."""
    for name in forbidden:
        d = w.docs[name]
        for needle in (SECRETS[name], TITLES[name], str(d.id), str(d.ver)):
            assert needle not in text, f"{cell}: {needle!r} of document {name} leaked"


def forbidden_for(who: str) -> set[str]:
    return set(DOCS) - readable(who)


# -- dense, BM25, hybrid, rerank -----------------------------------------------------------------

@pytest.mark.parametrize("who", WHO)
async def test_dense_retrieval_returns_exactly_the_readable_documents(shared: World, who) -> None:
    assert await dense_docs(shared, shared.principals[who]) == readable(who), who


@pytest.mark.parametrize("who", WHO)
async def test_bm25_retrieval_returns_exactly_the_readable_documents(shared: World, who) -> None:
    assert await bm25_docs(shared, shared.principals[who]) == readable(who), who


@pytest.mark.parametrize("who", WHO)
async def test_hybrid_retrieval_returns_exactly_the_readable_documents(shared: World, who) -> None:
    assert await hybrid_docs(shared, shared.principals[who]) == readable(who), who


@pytest.mark.parametrize("who", WHO)
async def test_the_reranker_is_only_ever_handed_readable_passages(shared: World, who) -> None:
    class Recording:
        name, model, revision = "local", "fake/rerank", "r"

        def __init__(self) -> None:
            self.passages: list[str] = []

        def score(self, query: str, passages):  # noqa: ANN001, ANN201
            self.passages += list(passages)
            return np.ones(len(passages), dtype=np.float32)

    reranker = Recording()
    retriever = Retriever(BowEmbedder(), RetrievalConfig(
        thresholds={"hybrid": 0.0, "hybrid_rerank": 0.0}), reranker)
    p = shared.principals[who]
    async with tenant_tx(shared.engine, p.workspace_id, p.user_id) as conn:
        res = await retriever.retrieve(conn, p, QUESTION)

    assert res.mode == "hybrid_rerank"
    assert shared.names_of(c.document_id for c in res.candidates) == readable(who)
    handed = "\n".join(reranker.passages)
    assert handed, "the reranker was never called, so this test would prove nothing"
    for name in readable(who):
        assert SECRETS[name] in handed, f"{who}: readable {name} never reached the reranker"
    assert_no_trace(handed, forbidden_for(who), shared, who)


# -- context assembly ----------------------------------------------------------------------------

async def chunk_rows(w: World, name: str) -> list[tuple]:
    return sql(w.database, "SELECT id, version_id, section_path FROM rag.chunks "
                           "WHERE document_id = %s", w.docs[name].id)


@pytest.mark.parametrize("who", WHO)
async def test_context_assembly_loads_nothing_of_a_forbidden_document(shared: World, who) -> None:
    p = shared.principals[who]
    for name in DOCS:
        rows = await chunk_rows(shared, name)
        assert rows, f"document {name} has no chunks: the fixture is broken"
        ids = [r[0] for r in rows]
        keys = [(r[1], tuple(r[2])) for r in rows]
        async with tenant_tx(shared.engine, p.workspace_id, p.user_id) as conn:
            chunks = await context_store.load_chunks(conn, p, ids)
            sections = await context_store.load_sections(conn, p, keys)
            infos = await context_store.load_version_info(conn, p, [r[1] for r in rows])
        cell = f"{who} x {name}"
        if can_read(who, name):
            assert chunks and sections and infos, cell
        else:
            assert chunks == [] and sections == {} and infos == {}, cell


async def test_a_hit_on_a_forbidden_chunk_is_dropped_before_the_prompt_is_built(
        shared: World) -> None:
    """A search result that went stale (access narrowed after the search) cannot reach the LLM."""
    p = shared.principals["MEMBER_NO_DEPT"]

    def hit(name: str) -> Candidate:
        r = sql(shared.database, "SELECT id, version_id FROM rag.chunks WHERE document_id = %s "
                                 "LIMIT 1", shared.docs[name].id)[0]
        return Candidate(r[0], shared.docs[name].id, r[1])

    async def run(hits: list[Candidate]):  # noqa: ANN202
        ctx = QAContext(question="q", principal=p)
        ctx.retrieval = RetrievalResult("hybrid", hits, 1.0, 0.0, True, hits=hits)
        step = BuildContextStep(shared.engine, ContextConfig(), ScriptedChain())
        return ctx, await step.run(ctx)

    ctx, decision = await run([hit("A"), hit("AB")])
    assert decision.kind is not DecisionKind.CONTINUE and decision.rule_id == "context.empty"
    assert ctx.sources == [] and ctx.source_texts == []

    ctx, decision = await run([hit("A"), hit("WS"), hit("AB")])
    assert decision.kind is DecisionKind.CONTINUE
    text = "\n".join(s.text for s in ctx.source_texts)
    assert SECRETS["WS"] in text
    assert_no_trace(text, {"A", "AB"}, shared, "MEMBER_NO_DEPT")


# -- the LLM, the stream, citations, stored turns ------------------------------------------------

@pytest.mark.parametrize("who", WHO)
async def test_the_llm_prompt_holds_only_readable_sources(shared: World, who) -> None:
    async with qa(shared) as api:
        await api.ask(shared.principals[who])
        prompt = api.prompt()
    for name in readable(who):
        assert SECRETS[name] in prompt, f"{who}: readable {name} is missing from the prompt"
    assert_no_trace(prompt, forbidden_for(who), shared, who)


@pytest.mark.parametrize("who", WHO)
async def test_the_stream_and_the_citations_hold_only_readable_documents(
        shared: World, who) -> None:
    async with qa(shared) as api:
        text, events = await api.ask(shared.principals[who])
    assert names(events)[-1] == "done" and data(events, "done")["outcome"] == "ANSWERED"
    cited = {c["documentId"] for c in data(events, "citations")}
    assert cited == {str(shared.docs[n].id) for n in readable(who)}, who
    assert_no_trace(text, forbidden_for(who), shared, who)


@pytest.mark.parametrize("who", WHO)
async def test_the_stored_turn_and_the_reopened_conversation_hold_only_readable_documents(
        shared: World, who) -> None:
    p = shared.principals[who]
    async with qa(shared) as api:
        _, events = await api.ask(p)
        conversation_id = data(events, "meta")["conversationId"]
        reopened = await api.conversation(p, conversation_id)

    allowed_ids = {shared.docs[n].id for n in readable(who)}
    who_rows = (shared.ws, p.user_id)
    answers = sql(shared.database,
                  "SELECT content, context_sources FROM rag.messages WHERE workspace_id = %s "
                  "AND user_id = %s AND role = 'ASSISTANT'", *who_rows)
    assert answers
    sourced = {UUID(s["documentId"]) for _, srcs in answers for s in srcs or []}
    cited = {r[0] for r in sql(shared.database,
                               "SELECT mc.document_id FROM rag.message_citations mc "
                               "JOIN rag.messages m ON m.id = mc.message_id "
                               "WHERE m.workspace_id = %s AND m.user_id = %s", *who_rows)}
    retrieved = {r[0] for r in sql(shared.database,
                                   "SELECT k.document_id FROM rag.retrieval_results r "
                                   "JOIN rag.messages m ON m.id = r.message_id "
                                   "JOIN rag.chunks k ON k.id = r.chunk_id "
                                   "WHERE m.workspace_id = %s AND m.user_id = %s", *who_rows)}
    assert sourced and cited and retrieved
    assert sourced <= allowed_ids and cited <= allowed_ids and retrieved <= allowed_ids, who
    assert_no_trace("\n".join(a for a, _ in answers), forbidden_for(who), shared, who)
    assert reopened.status_code == 200
    assert_no_trace(reopened.text, forbidden_for(who), shared, who)
    assert "hidden" not in reopened.text


@pytest.mark.parametrize("who", WHO)
async def test_a_refusal_names_only_readable_documents_as_nearest(shared: World, who) -> None:
    async with qa(shared, thresholds={"hybrid": 1.01}) as api:
        text, events = await api.ask(shared.principals[who])
    refusal = data(events, "refusal")
    assert refusal["reason"] == "NO_EVIDENCE" and "delta" not in names(events)
    nearest = {d["title"] for d in refusal["nearestDocuments"]}
    assert nearest == {TITLES[n] for n in readable(who)}, who
    assert_no_trace(text, forbidden_for(who), shared, who)


@pytest.mark.parametrize("who", WHO)
async def test_the_content_endpoint_follows_the_matrix(shared: World, who) -> None:
    p = shared.principals[who]
    for name in DOCS:
        resp = await content_status(shared, p, shared.docs[name])
        cell = f"{who} x {name}"
        if can_read(who, name):
            assert resp.status_code == 200 and SECRETS[name] in resp.json()["markdown"], cell
        else:
            assert resp.status_code == 404, f"{cell}: never 403, the document must look absent"
            assert_no_trace(resp.text, {name}, shared, cell)


# -- filter before LIMIT ---------------------------------------------------------------------------

FILLER = ("quy định này áp dụng cho toàn bộ nhân viên trong công ty theo hướng dẫn của ban quản "
          "lý và được xem xét hằng năm")


async def test_the_access_filter_runs_before_limit_so_forbidden_chunks_never_shrink_the_result(
        engine, keypair, database) -> None:  # noqa: ANN001
    """Many forbidden chunks match the question better than any allowed one. With a pool of 5 a
    filter applied after the top-k would leave the asker with nothing; applied before it, they
    still get 5 chunks, all of them readable."""
    ws, dept = uuid4(), uuid4()
    store, embedder = FakeStore(), BowEmbedder()
    deps = IngestDeps(engine=engine, store=store, embedder=embedder, tokenizer=Words(),
                      chunk_config=ChunkConfig(), max_attempts=3, backoff_base_seconds=0)
    forbidden_doc, open_doc = uuid4(), uuid4()
    forbidden_text = "# Mật khẩu kho\n\n" + "".join(
        f"## {k}. Phần {k}\n\nMật khẩu kho dữ liệu phần {k}. {FILLER}\n\n" for k in range(40))
    open_text = "# Kho chung\n\n" + "".join(
        f"## {k}. Mục {k}\n\nKho dữ liệu mục {k}. {FILLER}\n\n" for k in range(40))
    async with _app(engine, keypair) as client:
        await ingest(client, store, body(ws, forbidden_doc, uuid4(), "Mật khẩu kho",
                                         visibility="DEPARTMENTS", departments=[dept]),
                     forbidden_text)
        await ingest(client, store, body(ws, open_doc, uuid4(), "Kho chung"), open_text)
        assert await drain(deps, 600, None) == 2

    def count(doc: UUID) -> int:
        return sql(database, "SELECT count(*) FROM rag.chunks WHERE document_id = %s", doc)[0][0]

    pool = 5
    assert count(forbidden_doc) >= 2 * pool and count(open_doc) >= 2 * pool, "fixture too small"
    cfg = dict(candidate_pool=pool, rerank_pool=pool, context_k=pool)
    retriever = Retriever(BowEmbedder(), RetrievalConfig(thresholds={"hybrid": 0.0}, **cfg))
    qvec = BowEmbedder().embed([QUESTION], is_query=True)[0]
    terms = tokenize(QUESTION, role="query")

    async def run(p: Principal):  # noqa: ANN202
        async with tenant_tx(engine, ws, p.user_id) as conn:
            dense = await search.dense(conn, p, qvec, model=IDENTITY[0], revision=IDENTITY[1],
                                       pool=pool)
            lexical = await search.bm25(conn, p, terms, pool=pool)
            hybrid = await retriever.retrieve(conn, p, QUESTION)
        return dense, lexical, hybrid

    # Control: someone who may read both gets the forbidden chunks, which therefore do outrank.
    insider = Principal(uuid4(), ws, "MEMBER", dept)
    dense, lexical, hybrid = await run(insider)
    assert {h.document_id for h in dense} == {forbidden_doc}
    assert {h.document_id for h in lexical} == {forbidden_doc}

    outsider = Principal(uuid4(), ws, "MEMBER")
    dense, lexical, hybrid = await run(outsider)
    assert len(dense) == pool and {h.document_id for h in dense} == {open_doc}
    assert len(lexical) == pool and {h.document_id for h in lexical} == {open_doc}
    assert len(hybrid.candidates) == pool and len(hybrid.hits) == pool
    assert {c.document_id for c in hybrid.candidates} == {open_doc}


# -- changes of access ---------------------------------------------------------------------------

async def put_access(w: World, name: str, visibility: str, departments: list[UUID],
                     revision: int) -> bool:
    resp = await w.client.put(
        f"/internal/document-access/{w.docs[name].id}", headers=internal(),
        json={"workspaceId": str(w.ws), "visibility": visibility,
              "departmentIds": [str(d) for d in departments], "accessRevision": revision})
    assert resp.status_code == 200, resp.text
    return resp.json()["applied"]


async def channels(w: World, p: Principal, name: str) -> dict[str, bool]:
    """Whether the asker can reach one document through each channel right now."""
    async with qa(w) as api:
        _, events = await api.ask(p)
        prompt = api.prompt()
    return {
        "dense": name in await dense_docs(w, p),
        "bm25": name in await bm25_docs(w, p),
        "hybrid": name in await hybrid_docs(w, p),
        "content": (await content_status(w, p, w.docs[name])).status_code == 200,
        "prompt": SECRETS[name] in prompt,
        "stream": SECRETS[name] in "".join(d["text"] for n, d in events if n == "delta"),
    }


async def test_a_narrowing_ai_service_has_not_received_is_a_known_window_then_closes(
        fresh: World) -> None:
    outsider = fresh.principals["MEMBER_B"]
    # Core-api already narrowed WS to [A], but the ACCESS_UPDATED event has not arrived: the old
    # scope is still in force here (ADR-007 §5, "có hiệu lực khi ai-service nhận cập nhật").
    # This is a documented window, not fail-closed.
    assert all((await channels(fresh, outsider, "WS")).values())

    assert await put_access(fresh, "WS", "DEPARTMENTS", [fresh.dept_a], revision=2) is True

    for who in ("MEMBER_B", "MEMBER_NO_DEPT"):
        reach = await channels(fresh, fresh.principals[who], "WS")
        assert not any(reach.values()), f"{who} still reaches WS after the update: {reach}"
    for who in ("OWNER", "ADMIN", "MEMBER_A"):
        reach = await channels(fresh, fresh.principals[who], "WS")
        assert all(reach.values()), f"{who} lost WS after the update: {reach}"
    # The documents that were not narrowed are untouched.
    assert all((await channels(fresh, outsider, "AB")).values())


async def test_a_stale_or_equal_access_revision_never_widens_access(fresh: World) -> None:
    outsider = fresh.principals["MEMBER_NO_DEPT"]
    assert await put_access(fresh, "WS", "DEPARTMENTS", [fresh.dept_a], revision=2) is True
    assert not any((await channels(fresh, outsider, "WS")).values())

    for revision in (2, 1, 0):
        assert await put_access(fresh, "WS", "WORKSPACE", [], revision=revision) is False
        reach = await channels(fresh, outsider, "WS")
        assert not any(reach.values()), f"revision {revision} widened access: {reach}"

    # The guard is the revision, not a blanket refusal: a newer one is applied.
    assert await put_access(fresh, "WS", "WORKSPACE", [], revision=3) is True
    assert all((await channels(fresh, outsider, "WS")).values())


async def test_an_answer_built_from_a_document_narrowed_away_is_hidden_when_reopened(
        fresh: World) -> None:
    member_b, member_a = fresh.principals["MEMBER_B"], fresh.principals["MEMBER_A"]
    async with qa(fresh) as api:
        _, events_b = await api.ask(member_b)
        _, events_a = await api.ask(member_a)
        cid_b = data(events_b, "meta")["conversationId"]
        cid_a = data(events_a, "meta")["conversationId"]
        before = (await api.conversation(member_b, cid_b)).json()["messages"]
        assert "hidden" not in before[1] and SECRETS["WS"] in before[1]["content"]

        assert await put_access(fresh, "WS", "DEPARTMENTS", [fresh.dept_a], revision=2) is True

        after = await api.conversation(member_b, cid_b)
        shown = after.json()["messages"]
        assert shown[0]["content"] == QUESTION  # the question stays
        assert shown[1]["hidden"] is True and shown[1]["reason"] == "ACCESS_REVOKED"
        assert "content" not in shown[1] and "citations" not in shown[1]
        assert_no_trace(after.text, {"WS"}, fresh, "reopened by MEMBER_B")
        # Member A may still read every source of the same kind of answer.
        mine = (await api.conversation(member_a, cid_a)).json()["messages"]
        assert "hidden" not in mine[1] and SECRETS["WS"] in mine[1]["content"]


async def test_the_rewrite_call_never_receives_an_answer_built_from_a_narrowed_document(
        fresh: World) -> None:
    member_b = fresh.principals["MEMBER_B"]
    async with qa(fresh, rewrite=QUESTION) as api:
        _, first = await api.ask(member_b)  # built from WS and AB
        cid = data(first, "meta")["conversationId"]
        assert await put_access(fresh, "WS", "DEPARTMENTS", [fresh.dept_a], revision=2) is True

        # Turn 1 is now hidden, so there is no history to rewrite and the LLM is not called.
        _, second = await api.ask(member_b, FOLLOWUP, cid)
        assert api.rewrite.calls == []
        assert SECRETS["WS"] not in api.prompt() and SECRETS["AB"] in api.prompt()
        assert data(second, "done")["outcome"] == "ANSWERED"  # built from AB only

        # Turn 2 is readable, turn 1 is not: the rewrite sees the former and never the latter.
        _, third = await api.ask(member_b, FOLLOWUP, cid)
        assert data(third, "done")["outcome"] == "ANSWERED"
        assert [c["kind"] for c in api.rewrite.calls] == ["complete"]
        rewrite_prompt = "\n".join(m["content"] for m in api.rewrite.calls[0]["messages"])
        assert SECRETS["AB"] in rewrite_prompt, "turn 2 should be history: the test proves nothing"
        assert_no_trace(rewrite_prompt, {"WS"}, fresh, "rewrite prompt")


# -- fail closed ---------------------------------------------------------------------------------

async def test_a_document_without_an_access_row_is_readable_by_nobody_not_even_the_owner(
        fresh: World) -> None:
    sql(fresh.database, "DELETE FROM rag.document_access WHERE document_id = %s",
        fresh.docs["WS"].id)
    chunks = sql(fresh.database, "SELECT count(*) FROM rag.chunks WHERE document_id = %s",
                 fresh.docs["WS"].id)[0][0]
    assert chunks > 0, "the chunks must still exist for this to mean anything"
    for who in WHO:
        reach = await channels(fresh, fresh.principals[who], "WS")
        assert not any(reach.values()), f"{who}: {reach}"
        # Control: the other two documents are still reachable as the matrix says.
        for name in ("A", "AB"):
            assert all((await channels(fresh, fresh.principals[who], name)).values()) \
                == can_read(who, name)


async def test_a_version_that_is_not_activated_yet_is_readable_by_nobody_not_even_the_owner(
        fresh: World) -> None:
    doc, ver = uuid4(), uuid4()
    title, secret = "Quy trình mới NEW-7421", "SECRET_NEW_7421"
    await ingest(fresh.client, fresh.store, body(fresh.ws, doc, ver, title),
                 f"# {title}\n\n## 1. Truy cập\n\nMật khẩu kho dữ liệu mới là {secret}.\n")
    # Queued, not processed: there are no chunks and no active version.
    fresh.docs["NEW"] = Doc(doc, ver, "NEW")
    SECRETS["NEW"], TITLES["NEW"] = secret, title
    try:
        for who in WHO:
            p = fresh.principals[who]
            reach = await channels(fresh, p, "NEW")
            assert not any(reach.values()), f"{who}: {reach}"
        # Once processed it becomes readable, so the check above was about activation.
        assert await drain(fresh.deps, 600, None) == 1
        assert all((await channels(fresh, fresh.principals["MEMBER_NO_DEPT"], "NEW")).values())
    finally:
        SECRETS.pop("NEW", None)
        TITLES.pop("NEW", None)


async def test_a_deleted_document_is_readable_by_nobody_not_even_the_owner(fresh: World) -> None:
    doc = fresh.docs["WS"]
    resp = await fresh.client.delete(f"/internal/documents/{doc.id}?workspaceId={fresh.ws}",
                                     headers=internal())
    assert resp.status_code == 200
    for who in WHO:
        reach = await channels(fresh, fresh.principals[who], "WS")
        assert not any(reach.values()), f"{who}: {reach}"


# -- the only cache ----------------------------------------------------------------------------

async def test_there_is_no_answer_or_retrieval_cache_and_the_embedding_cache_holds_no_text(
        shared: World, database) -> None:  # noqa: ANN001
    """ADR-007 §4.5: no answer or retrieval cache exists, so there is no cache key to widen.

    ``rag.suggestion_cache`` (V2-25, metadata suggestions) is in the schema but nothing writes it
    yet. It is keyed by ``workspace_id`` only, so when V2-25 starts filling it this test fails and
    the author must decide how a suggestion derived from a restricted document is shared.
    """
    tables = {r[0] for r in sql(
        database, "SELECT table_name FROM information_schema.tables "
                  "WHERE table_schema = 'rag' AND table_name ILIKE '%%cache%%'")}
    assert tables == {"embedding_cache", "suggestion_cache"}
    assert sql(database, "SELECT count(*) FROM rag.suggestion_cache")[0][0] == 0, (
        "V2-25 now writes suggestion_cache: add a department case for it to this suite")

    columns = dict(sql(database, "SELECT column_name, data_type FROM information_schema.columns "
                                 "WHERE table_schema = 'rag' AND table_name = 'embedding_cache'"))
    texty = ("text", "character varying", "jsonb", "json")
    text_columns = {c for c, t in columns.items() if t in texty}
    assert text_columns == {"model", "revision"}  # identifiers of the model, never content
    assert set(columns) == {"model", "revision", "content_sha256", "embedding", "created_at"}
    assert "workspace_id" not in columns  # a hash of the content cannot be traced to a workspace
    key = {r[0] for r in sql(database, "SELECT a.attname FROM pg_index i JOIN pg_attribute a "
                                       "ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey) "
                                       "WHERE i.indrelid = 'rag.embedding_cache'::regclass "
                                       "AND i.indisprimary")}
    assert key == {"model", "revision", "content_sha256"}

    rows = sql(database, "SELECT c::text FROM rag.embedding_cache c")
    assert rows, "ingestion fills the cache, so an empty table means the test looks at nothing"
    dump = " ".join(r[0] for r in rows)
    assert_no_trace(dump, set(DOCS), shared, "embedding_cache")
