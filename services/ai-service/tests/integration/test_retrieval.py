"""V2-09 step 2 on real Postgres: hybrid retrieval, access filter, four scores, internal access
and delete endpoints, the content endpoint, the startup index check and ``admin reindex``.

Every test ingests into a fresh workspace through the internal API and the worker, with a
bag-of-words embedder so that dense neighbours are predictable without a model download.
"""
from __future__ import annotations

import dataclasses
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import jwt
import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from fakes import BowEmbedder, Words
from sopilot_ai.admin import reindex
from sopilot_ai.api.app import create_app
from sopilot_ai.auth.jwt import AUDIENCE, ISSUER, TokenVerifier
from sopilot_ai.config import Settings
from sopilot_ai.db.engine import system_tx, tenant_tx
from sopilot_ai.db.repositories import reindex as reindex_repo
from sopilot_ai.db.repositories import retrieval_results
from sopilot_ai.docproc import ChunkConfig
from sopilot_ai.docproc.render import NORMALIZER_VERSION
from sopilot_ai.ingest.handler import IngestDeps
from sopilot_ai.providers.registry import RetrievalConfig
from sopilot_ai.retrieval import search
from sopilot_ai.retrieval.access_filter import Principal
from sopilot_ai.retrieval.lexical import BM25, lexical_len, tokenize
from sopilot_ai.retrieval.retriever import Retriever
from sopilot_ai.worker import drain

TOKEN = "test-internal-token"
IDENTITY = ("fake/bge-m3", "test-rev")

PURCHASE = """---
code: QT-MH-01
---
# Quy trình mua hàng

## 1. Mục đích

Quy định cách lập và duyệt đề nghị mua hàng trong công ty để kiểm soát chi phí mua sắm.

## 2. Nội dung

| Bước | Trách nhiệm | Mô tả |
|---|---|---|
| 1 | Nhân viên | Lập phiếu đề nghị mua hàng |
| 2 | Trưởng phòng | Duyệt đề nghị mua hàng trong hai ngày làm việc |
"""

HIRING = """# Quy trình tuyển dụng

## 1. Mục đích

Quy định cách tuyển dụng nhân sự mới, phỏng vấn ứng viên và ký hợp đồng thử việc.

## 2. Trách nhiệm

Phòng nhân sự đăng tin tuyển dụng; trưởng bộ phận phỏng vấn ứng viên.
"""

LAPTOP = """# Laptop request procedure

## 1. Scope

Employees request a laptop through the IT portal. A laptop request needs manager approval.

## 2. Delivery

IT prepares the laptop within five working days after the laptop request is approved.
"""

SECRET = """# Kho dữ liệu

## 1. Truy cập

Mật khẩu kho dữ liệu là XYZSECRET và chỉ phòng tài chính được biết mật khẩu này.
"""


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def get(self, key: str) -> bytes:
        return self.objects[key]


@dataclasses.dataclass
class Corpus:
    ws: UUID
    finance: UUID  # department that may read SECRET
    docs: dict[str, tuple[UUID, UUID]]  # name -> (document_id, version_id)

    def principal(self, role: str = "OWNER", dept: UUID | None = None) -> Principal:
        return Principal(uuid4(), self.ws, role, dept)


@pytest.fixture(scope="module")
def keypair():  # noqa: ANN201
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key()


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def embedder() -> BowEmbedder:
    return BowEmbedder()


@pytest.fixture
def deps(engine, store: FakeStore, embedder: BowEmbedder) -> IngestDeps:
    return IngestDeps(engine=engine, store=store, embedder=embedder, tokenizer=Words(),
                      chunk_config=ChunkConfig(), max_attempts=3, backoff_base_seconds=0)


@pytest.fixture
async def client(engine, keypair) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings.model_validate({"SOPILOT_DB_URL": "postgresql://unused",
                                        "SOPILOT_INTERNAL_TOKEN": TOKEN})
    app = create_app(settings, engine, embedding_identity=IDENTITY,
                     token_verifier=TokenVerifier(key_for=lambda _t: keypair[1]))
    app.state.engine = engine  # ASGITransport does not run the lifespan
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://ai") as c:
        yield c


def internal(key: UUID | None = None) -> dict[str, str]:
    return {"X-Internal-Token": TOKEN, "Idempotency-Key": str(key or uuid4())}


def bearer(keypair, p: Principal) -> dict[str, str]:  # noqa: ANN001
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": ["sopilot-core", AUDIENCE], "sub": str(p.user_id),
              "wid": str(p.workspace_id), "wrole": p.role,
              "wdept": str(p.department_id) if p.department_id else None,
              "jti": str(uuid4()), "iat": now, "exp": now + 900}
    return {"Authorization": "Bearer " + jwt.encode(claims, keypair[0], algorithm="RS256")}


def body(ws: UUID, doc: UUID, ver: UUID, title: str, *, version_no: int = 1,
         visibility: str = "WORKSPACE", departments: list[UUID] | None = None,
         revision: int = 1) -> dict[str, Any]:
    return {
        "workspaceId": str(ws), "documentId": str(doc), "versionId": str(ver),
        "versionNo": version_no, "objectKey": f"ws/{ws}/doc/{doc}/v/{ver}", "sha256": "0" * 64,
        "attempt": 0, "fileType": "MD", "mimeType": "text/markdown", "title": title,
        "access": {"visibility": visibility,
                   "departmentIds": [str(d) for d in departments or []],
                   "accessRevision": revision},
    }


async def ingest(client, store, b: dict[str, Any], text_: str) -> None:  # noqa: ANN001
    store.objects[b["objectKey"]] = text_.encode("utf-8")
    resp = await client.post("/internal/ingestions", json=b, headers=internal())
    assert resp.status_code == 202, resp.text


def sql(database, query: str, *params: Any) -> list[tuple]:  # noqa: ANN001
    with database.superuser() as conn:
        cur = conn.execute(query, params)
        return cur.fetchall() if cur.description else []


@pytest.fixture
async def corpus(client, store, deps) -> Corpus:  # noqa: ANN001
    ws, finance = uuid4(), uuid4()
    docs = {}
    for name, title, text_, vis in (("purchase", "Quy trình mua hàng", PURCHASE, "WORKSPACE"),
                                    ("hiring", "Quy trình tuyển dụng", HIRING, "WORKSPACE"),
                                    ("laptop", "Laptop request procedure", LAPTOP, "WORKSPACE"),
                                    ("secret", "Kho dữ liệu", SECRET, "DEPARTMENTS")):
        doc, ver = uuid4(), uuid4()
        await ingest(client, store, body(ws, doc, ver, title, visibility=vis,
                                         departments=[finance] if vis == "DEPARTMENTS" else None),
                     text_)
        docs[name] = (doc, ver)
    assert await drain(deps, 600, None) == 4
    return Corpus(ws, finance, docs)


async def run(engine, retriever: Retriever, p: Principal, query: str, **kw):  # noqa: ANN001, ANN201
    async with tenant_tx(engine, p.workspace_id, p.user_id) as conn:
        return await retriever.retrieve(conn, p, query, **kw)


def docs_of(result, corpus: Corpus) -> list[str]:  # noqa: ANN001
    names = {doc: name for name, (doc, _) in corpus.docs.items()}
    return [names[c.document_id] for c in result.candidates]


# -- BM25 in SQL = in-memory reference -------------------------------------------------------

async def test_bm25_sql_matches_in_memory_reference(engine, database, corpus: Corpus) -> None:
    rows = sql(database, "SELECT id, index_text FROM rag.chunks WHERE workspace_id = %s "
                         "ORDER BY id", corpus.ws)
    ids, texts = [r[0] for r in rows], [r[1] for r in rows]
    ref = BM25([tokenize(t) for t in texts], lengths=[lexical_len(t) for t in texts])
    owner = corpus.principal()
    for query in ("quy trình mua hàng", "quy trinh tuyen dung", "laptop request approval",
                  "trưởng phòng duyệt đề nghị", "XYZSECRET"):
        expected = ref.scores(tokenize(query, role="query"))
        async with tenant_tx(engine, corpus.ws) as conn:
            hits = await search.bm25(conn, owner, tokenize(query, role="query"), pool=100)
        got = {h.chunk_id: h.score for h in hits}
        assert set(got) == {ids[i] for i in np.flatnonzero(expected > 0)}, query
        for i, chunk_id in enumerate(ids):
            if expected[i] > 0:
                assert got[chunk_id] == pytest.approx(float(expected[i]), rel=1e-4), query


async def test_unaccented_query_matches_accented_text(engine, corpus: Corpus) -> None:
    bm25_only = Retriever(BowEmbedder(), RetrievalConfig(mode="bm25"))
    owner = corpus.principal()
    vi = await run(engine, bm25_only, owner, "quy trinh tuyen dung")
    assert docs_of(vi, corpus)[0] == "hiring"
    en = await run(engine, bm25_only, owner, "laptop request")
    assert docs_of(en, corpus)[0] == "laptop"
    assert vi.mode == "bm25" and vi.gate_score is None and vi.passed  # bm25 never refuses
    assert all(c.dense_score is None and c.bm25_score > 0 for c in vi.candidates)


# -- access filter (FR-25, FR-29) ------------------------------------------------------------

async def test_access_filter_applies_before_limit(engine, corpus: Corpus) -> None:
    secret_doc = corpus.docs["secret"][0]
    tight = RetrievalConfig(mode="hybrid", candidate_pool=1, rerank_pool=5,
                            thresholds={"hybrid": 0.0})
    retriever = Retriever(BowEmbedder(), tight)
    query = "mật khẩu kho dữ liệu XYZSECRET"

    outsider = corpus.principal("MEMBER", uuid4())
    for p in (outsider, corpus.principal("MEMBER")):
        res = await run(engine, retriever, p, query)
        # Filtered before LIMIT: the best allowed chunk still fills the pool of 1.
        assert res.candidates and all(c.document_id != secret_doc for c in res.candidates)
        async with tenant_tx(engine, corpus.ws) as conn:
            qvec = BowEmbedder().embed([query], is_query=True)[0]
            dense = await search.dense(conn, p, qvec, model=IDENTITY[0], revision=IDENTITY[1],
                                       pool=1)
            lexical = await search.bm25(conn, p, tokenize(query, role="query"), pool=1)
        assert len(dense) == 1 and dense[0].document_id != secret_doc
        assert all(h.document_id != secret_doc for h in lexical)

    for p in (corpus.principal("MEMBER", corpus.finance), corpus.principal("ADMIN"),
              corpus.principal("OWNER")):
        res = await run(engine, retriever, p, query)
        assert res.candidates[0].document_id == secret_doc

    stranger = Principal(uuid4(), uuid4(), "OWNER")  # another workspace
    res = await run(engine, retriever, stranger, query)
    assert res.candidates == [] and not res.passed


# -- fusion, gate, four scores ---------------------------------------------------------------

async def test_hybrid_candidates_always_have_dense_score(engine, database, corpus) -> None:
    # With one candidate per branch and equal weights the dense-only and BM25-only candidates tie
    # on RRF and the tie breaks on the random chunk UUID; weigh dense higher so the BM25-only
    # candidate always ranks second.
    cfg = RetrievalConfig(mode="hybrid", candidate_pool=1, rerank_pool=10,
                          rrf_weights=(2.0, 1.0), thresholds={"hybrid": 0.0})
    retriever = Retriever(BowEmbedder(), cfg)
    owner = corpus.principal()
    bm25_only_seen = False
    for query in ("laptop laptop quy trình mua hàng duyệt đề nghị",
                  "ứng viên phỏng vấn laptop request", "manager approval mua sắm chi phí"):
        res = await run(engine, retriever, owner, query)
        assert all(c.dense_score is not None for c in res.candidates)
        qvec = BowEmbedder().embed([query], is_query=True)[0]
        for c in res.candidates:
            emb = sql(database, "SELECT embedding::text FROM rag.chunks WHERE id = %s",
                      c.chunk_id)[0][0]
            vec = np.array([float(x) for x in emb.strip("[]").split(",")], dtype=np.float32)
            assert c.dense_score == pytest.approx(float(vec @ qvec), abs=1e-5)
            bm25_only_seen |= c.bm25_score is not None and c.rank > 1
        assert res.gate_score == res.candidates[0].dense_score
    assert bm25_only_seen  # at least one candidate came from the BM25 branch only


async def test_doc_code_in_question_boosts_matching_version(engine, corpus: Corpus) -> None:
    owner = corpus.principal()
    query = "QT-MH-01 trưởng phòng duyệt trong bao lâu"
    plain = await run(engine, Retriever(BowEmbedder(), RetrievalConfig(doc_code_boost=0.0)),
                      owner, query)
    boosted = await run(engine, Retriever(BowEmbedder(), RetrievalConfig(doc_code_boost=0.02)),
                        owner, query)
    assert boosted.doc_codes == {"QT-MH-01"}
    before = {c.chunk_id: c.fusion_score for c in plain.candidates}
    purchase = corpus.docs["purchase"][0]
    for c in boosted.candidates:
        if c.document_id == purchase:
            assert c.doc_code_match
            assert c.fusion_score == pytest.approx(before[c.chunk_id] + 0.02)
        else:
            assert not c.doc_code_match and c.fusion_score == pytest.approx(before[c.chunk_id])
    assert boosted.candidates[0].document_id == purchase


async def test_gate_threshold_and_saved_scores(engine, database, corpus: Corpus) -> None:
    owner = corpus.principal()
    query = "quy trình tuyển dụng ứng viên"
    low = await run(engine, Retriever(BowEmbedder(), RetrievalConfig(
        context_k=2, thresholds={"hybrid": 0.0})), owner, query)
    high = await run(engine, Retriever(BowEmbedder(), RetrievalConfig(
        thresholds={"hybrid": 1.01})), owner, query)
    assert low.passed and len(low.hits) == 2 and low.hits == low.candidates[:2]
    assert not high.passed and high.hits == [] and high.gate_score == low.gate_score
    assert [c.rank for c in low.candidates] == list(range(1, len(low.candidates) + 1))

    conv, msg = uuid4(), uuid4()
    async with tenant_tx(engine, corpus.ws, owner.user_id) as conn:
        from sqlalchemy import text

        await conn.execute(text("INSERT INTO rag.conversations (id, workspace_id, user_id, title) "
                                "VALUES (:c, :w, :u, 't')"),
                           {"c": conv, "w": corpus.ws, "u": owner.user_id})
        await conn.execute(text("INSERT INTO rag.messages (id, workspace_id, conversation_id, "
                                "user_id, role, content) VALUES (:m, :w, :c, :u, 'USER', 'q')"),
                           {"m": msg, "w": corpus.ws, "c": conv, "u": owner.user_id})
        n = await retrieval_results.save(conn, corpus.ws, msg, low)
    rows = sql(database, "SELECT rank, dense_score, bm25_score, fusion_score, rerank_score, "
                         "in_context FROM rag.retrieval_results WHERE message_id = %s "
                         "ORDER BY rank", msg)
    assert n == len(rows) == len(low.candidates)
    assert all(r[1] is not None and r[3] is not None and r[4] is None for r in rows)
    assert [r[5] for r in rows] == [True, True] + [False] * (len(rows) - 2)


async def test_rerank_runs_before_gate_and_reorders(engine, corpus: Corpus) -> None:
    class KeywordRerank:
        name, model, revision = "local", "fake/rerank", "r"

        def __init__(self) -> None:
            self.calls = 0

        def score(self, query: str, passages):  # noqa: ANN001, ANN201
            self.calls += 1
            return np.array([0.9 if "laptop" in p.lower() else 0.1 for p in passages],
                            dtype=np.float32)

    rerank = KeywordRerank()
    cfg = RetrievalConfig(thresholds={"hybrid": 0.99, "hybrid_rerank": 0.5})
    res = await run(engine, Retriever(BowEmbedder(), cfg, rerank), corpus.principal(),
                    "quy trình mua hàng laptop")
    assert rerank.calls == 1 and res.mode == "hybrid_rerank"
    assert all(c.rerank_score is not None for c in res.candidates)
    assert docs_of(res, corpus)[0] == "laptop" and res.gate_score == pytest.approx(0.9)
    assert res.passed  # gated on rerank_score with the hybrid_rerank threshold
    scores = [c.rerank_score for c in res.candidates]
    assert scores == sorted(scores, reverse=True)


# -- internal access update and delete -------------------------------------------------------

async def test_access_update_moves_forward_and_changes_retrieval(client, engine, corpus) -> None:
    doc = corpus.docs["hiring"][0]
    member = corpus.principal("MEMBER", uuid4())
    retriever = Retriever(BowEmbedder(), RetrievalConfig(mode="bm25"))
    assert "hiring" in docs_of(await run(engine, retriever, member, "tuyển dụng"), corpus)

    url = f"/internal/document-access/{doc}"
    narrow = {"workspaceId": str(corpus.ws), "visibility": "DEPARTMENTS",
              "departmentIds": [str(corpus.finance)], "accessRevision": 1}
    resp = await client.put(url, json=narrow, headers=internal())
    assert resp.json() == {"applied": False}  # not newer than the ingest revision 1
    key = uuid4()
    resp = await client.put(url, json={**narrow, "accessRevision": 2}, headers=internal(key))
    assert resp.status_code == 200 and resp.json() == {"applied": True}
    assert (await client.put(url, json={**narrow, "accessRevision": 3},
                             headers=internal(key))).json() == {"applied": False}  # same key
    assert "hiring" not in docs_of(await run(engine, retriever, member, "tuyển dụng"), corpus)
    finance = corpus.principal("MEMBER", corpus.finance)
    assert "hiring" in docs_of(await run(engine, retriever, finance, "tuyển dụng"), corpus)

    bad = await client.put(url, json={**narrow, "departmentIds": [], "accessRevision": 9},
                           headers=internal())
    assert bad.status_code == 422
    unknown = await client.put(f"/internal/document-access/{uuid4()}",
                               json={**narrow, "accessRevision": 9}, headers=internal())
    assert unknown.json() == {"applied": False}
    assert (await client.put(url, json=narrow)).status_code == 401


async def test_delete_document_removes_everything(client, engine, database, corpus) -> None:
    doc, ver = corpus.docs["purchase"]
    url = f"/internal/documents/{doc}?workspaceId={corpus.ws}"
    assert (await client.delete(url)).status_code == 401
    resp = await client.delete(url, headers=internal())
    assert resp.status_code == 200
    for table in ("document_access", "chunks", "extracted_documents", "ingestion_jobs"):
        assert sql(database, f"SELECT count(*) FROM rag.{table} WHERE document_id = %s",
                   doc) == [(0,)], table
    res = await run(engine, Retriever(BowEmbedder(), RetrievalConfig(mode="bm25")),
                    corpus.principal(), "quy trình mua hàng QT-MH-01")
    assert "purchase" not in docs_of(res, corpus)
    assert (await client.delete(url, headers=internal())).status_code == 200  # idempotent
    other = sql(database, "SELECT count(*) FROM rag.chunks WHERE workspace_id = %s", corpus.ws)
    assert other[0][0] > 0  # other documents untouched


# -- content endpoint (§7.3, FR-14, FR-31) ---------------------------------------------------

async def test_content_returns_only_the_active_readable_version(client, store, deps, keypair,
                                                               corpus) -> None:
    doc, v1 = corpus.docs["purchase"]
    owner = corpus.principal()
    url = f"/ai/v1/documents/{doc}/versions/{v1}/content"
    resp = await client.get(url, headers=bearer(keypair, owner))
    assert resp.status_code == 200
    data = resp.json()
    assert data["documentId"] == str(doc) and data["versionId"] == str(v1)
    assert data["fileType"] == "MD" and data["normalizerVersion"] == NORMALIZER_VERSION
    assert data["markdown"].startswith("# Quy trình mua hàng")
    assert data["pages"] == [] and isinstance(data["warnings"], list)
    assert isinstance(data["removedBlocks"], list)

    assert (await client.get(url)).status_code == 401
    # A replacement in progress: the new version is not readable, the active one still is.
    v2 = uuid4()
    await ingest(client, store, body(corpus.ws, doc, v2, "Quy trình mua hàng", version_no=2),
                 PURCHASE + "\nBổ sung.\n")
    queued = f"/ai/v1/documents/{doc}/versions/{v2}/content"
    assert (await client.get(queued, headers=bearer(keypair, owner))).status_code == 404
    assert (await client.get(url, headers=bearer(keypair, owner))).status_code == 200
    assert await drain(deps, 600, None) == 1
    assert (await client.get(queued, headers=bearer(keypair, owner))).status_code == 200
    assert (await client.get(url, headers=bearer(keypair, owner))).status_code == 404

    stranger = Principal(uuid4(), uuid4(), "OWNER")
    assert (await client.get(queued, headers=bearer(keypair, stranger))).status_code == 404

    secret_doc, secret_ver = corpus.docs["secret"]
    secret = f"/ai/v1/documents/{secret_doc}/versions/{secret_ver}/content"
    outsider = corpus.principal("MEMBER", uuid4())
    insider = corpus.principal("MEMBER", corpus.finance)
    assert (await client.get(secret, headers=bearer(keypair, outsider))).status_code == 404
    assert (await client.get(secret, headers=bearer(keypair, insider))).status_code == 200

    await client.delete(f"/internal/documents/{secret_doc}?workspaceId={corpus.ws}",
                        headers=internal())
    assert (await client.get(secret, headers=bearer(keypair, insider))).status_code == 404


async def test_content_of_failed_version_is_not_found(client, store, deps, keypair) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    await ingest(client, store, body(ws, doc, ver, "Rỗng"), "")
    await drain(deps, 600, None)
    p = Principal(uuid4(), ws, "OWNER")
    resp = await client.get(f"/ai/v1/documents/{doc}/versions/{ver}/content",
                            headers=bearer(keypair, p))
    assert resp.status_code == 404


# -- startup check and admin reindex (D2(e)) -------------------------------------------------

async def test_reindex_brings_stale_versions_back_in_step(client, engine, database, store,
                                                          deps, embedder) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    embedder.revision = "old-rev"
    await ingest(client, store, body(ws, doc, ver, "Quy trình tuyển dụng"), HIRING)
    assert await drain(deps, 600, None) == 1
    events_before = sql(database, "SELECT count(*) FROM rag.outbox_events WHERE aggregate_id = %s",
                        doc)[0][0]

    async with system_tx(engine) as conn:
        stale = await reindex_repo.stale_versions(conn, model=IDENTITY[0], revision=IDENTITY[1],
                                                  normalizer_version=NORMALIZER_VERSION)
    assert ver in {s.version_id for s in stale}
    health = (await client.get("/health")).json()
    assert health["status"] == "degraded" and health["staleVersions"] >= 1

    found, queued = await reindex(engine, *IDENTITY, dry_run=True)
    assert found >= 1 and queued == 0
    found, queued = await reindex(engine, *IDENTITY)
    assert queued == found >= 1
    embedder.revision = IDENTITY[1]
    assert await drain(deps, 600, None) == queued

    assert sql(database, "SELECT DISTINCT embedding_revision FROM rag.chunks "
                         "WHERE document_id = %s", doc) == [(IDENTITY[1],)]
    assert sql(database, "SELECT active_version_id FROM rag.document_access "
                         "WHERE document_id = %s", doc) == [(ver,)]
    events_after = sql(database, "SELECT count(*) FROM rag.outbox_events WHERE aggregate_id = %s",
                       doc)[0][0]
    assert events_after == events_before  # a reindex sends no status callback
    async with system_tx(engine) as conn:
        stale = await reindex_repo.stale_versions(conn, model=IDENTITY[0], revision=IDENTITY[1],
                                                  normalizer_version=NORMALIZER_VERSION)
    assert ver not in {s.version_id for s in stale}
    assert (await client.get("/health")).json() == {"status": "ok"}
