"""V2-09 step 1 on real Postgres: internal ingestion API, worker, activation, retries, outbox, RLS.

Each test uses fresh workspace/document ids, so tests share one database without interfering
(the claim function is global, so every test drains the queue it fills).
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text

from fakes import FakeEmbedder, Words
from sopilot_ai.api.app import create_app
from sopilot_ai.config import Settings
from sopilot_ai.db.engine import system_tx, tenant_tx
from sopilot_ai.db.repositories import jobs
from sopilot_ai.docproc import ChunkConfig
from sopilot_ai.ingest.handler import IngestDeps, handle_job
from sopilot_ai.ingest.storage import ObjectNotFound
from sopilot_ai.outbox.dispatcher import OutboxDispatcher
from sopilot_ai.worker import drain

TOKEN = "test-internal-token"

SOP_MD = """# Quy trình mua hàng

## 1. Mục đích

Quy định cách lập và duyệt đề nghị mua hàng trong công ty để kiểm soát chi phí mua sắm.

## 2. Phạm vi

Áp dụng cho mọi phòng ban có nhu cầu mua hàng hóa và dịch vụ phục vụ hoạt động.

## 3. Nội dung

| Bước | Trách nhiệm | Mô tả |
|---|---|---|
| 1 | Nhân viên | Lập phiếu đề nghị mua hàng |
| 2 | Trưởng phòng | Duyệt đề nghị và chuyển phòng mua hàng |
"""


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes | Exception] = {}

    def get(self, key: str) -> bytes:
        value = self.objects.get(key, ObjectNotFound(key))
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def deps(engine, store: FakeStore, embedder: FakeEmbedder) -> IngestDeps:
    return IngestDeps(engine=engine, store=store, embedder=embedder, tokenizer=Words(),
                      chunk_config=ChunkConfig(), max_attempts=3, backoff_base_seconds=0)


@pytest.fixture
async def client(engine) -> httpx.AsyncClient:
    settings = Settings.model_validate({"SOPILOT_DB_URL": "postgresql://unused",
                                        "SOPILOT_INTERNAL_TOKEN": TOKEN})
    app = create_app(settings, engine)
    app.state.engine = engine  # ASGITransport does not run the lifespan
    app.state.internal_token = TOKEN
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://ai") as c:
        yield c


def ingest_body(workspace: UUID, document: UUID, version: UUID, *, attempt: int = 0,
                version_no: int = 1, file_type: str = "MD", key: str | None = None,
                visibility: str = "WORKSPACE", revision: int = 1) -> dict[str, Any]:
    return {
        "workspaceId": str(workspace), "documentId": str(document), "versionId": str(version),
        "versionNo": version_no, "objectKey": key or f"ws/{workspace}/doc/{document}/v/{version}",
        "sha256": "0" * 64, "attempt": attempt, "fileType": file_type,
        "mimeType": "text/markdown", "originalName": "QT-MH-01.md", "title": "Quy trình mua hàng",
        "access": {"visibility": visibility,
                   "departmentIds": [str(uuid4())] if visibility == "DEPARTMENTS" else [],
                   "accessRevision": revision},
    }


async def post(client: httpx.AsyncClient, body: dict, key: UUID | None = None) -> httpx.Response:
    return await client.post("/internal/ingestions", json=body,
                             headers={"X-Internal-Token": TOKEN,
                                      "Idempotency-Key": str(key or uuid4())})


def sql(database, query: str, *params: Any) -> list[tuple]:
    with database.superuser() as conn:
        cur = conn.execute(query, params)
        return cur.fetchall() if cur.description else []


def status_events(database, document: UUID) -> list[dict]:
    rows = sql(database, "SELECT payload FROM rag.outbox_events WHERE aggregate_id = %s "
                         "ORDER BY created_at", document)
    return [r[0] for r in rows]


def job_row(database, version: UUID) -> dict:
    with database.superuser() as conn:
        cur = conn.cursor(row_factory=__import__("psycopg").rows.dict_row)
        return cur.execute("SELECT * FROM rag.ingestion_jobs WHERE version_id = %s",
                           (version,)).fetchone()


# -- internal API --------------------------------------------------------------------------------

async def test_internal_token_is_required(client: httpx.AsyncClient) -> None:
    body = ingest_body(uuid4(), uuid4(), uuid4())
    resp = await client.post("/internal/ingestions", json=body,
                             headers={"X-Internal-Token": "wrong", "Idempotency-Key": str(uuid4())})
    assert resp.status_code == 401
    resp = await client.post("/internal/ingestions", json=body,
                             headers={"Idempotency-Key": str(uuid4())})
    assert resp.status_code == 401


async def test_repeated_idempotency_key_does_nothing(client, database, deps) -> None:
    ws, doc, ver, key = uuid4(), uuid4(), uuid4(), uuid4()
    first = await post(client, ingest_body(ws, doc, ver), key)
    assert first.status_code == 202 and first.json() == {"queued": True}
    again = await post(client, ingest_body(ws, doc, ver, attempt=5), key)
    assert again.status_code == 202 and again.json() == {"queued": False}
    assert job_row(database, ver)["request_attempt"] == 0
    await drain(deps, 600, None)  # clean the queue for the next tests


async def test_access_revision_only_moves_forward(client, database, deps) -> None:
    ws, doc = uuid4(), uuid4()
    await post(client, ingest_body(ws, doc, uuid4(), revision=5, visibility="DEPARTMENTS"))
    await post(client, ingest_body(ws, doc, uuid4(), version_no=2, revision=4))
    assert sql(database, "SELECT visibility, access_revision FROM rag.document_access "
                         "WHERE document_id = %s", doc) == [("DEPARTMENTS", 5)]
    await post(client, ingest_body(ws, doc, uuid4(), version_no=3, revision=6))
    assert sql(database, "SELECT visibility, access_revision FROM rag.document_access "
                         "WHERE document_id = %s", doc) == [("WORKSPACE", 6)]
    await drain(deps, 600, None)


# -- ingest end to end --------------------------------------------------------------------------

async def test_ingest_markdown_end_to_end(client, database, deps, store, embedder) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    body = ingest_body(ws, doc, ver)
    store.objects[body["objectKey"]] = SOP_MD.encode("utf-8")
    assert (await post(client, body)).json() == {"queued": True}

    assert await drain(deps, 600, None) == 1
    job = job_row(database, ver)
    assert job["status"] == "DONE" and job["attempts"] == 1
    assert {"download_ms", "extract_ms", "chunk_ms", "embed_ms", "write_ms"} <= set(
        job["stage_timings"])

    chunks = sql(database, """
        SELECT workspace_id, document_id, version_id, ordinal, chunk_type, section_path,
               char_start, char_end, lang, embedding_provider, embedding_model, embedding_dim,
               embedding_revision, token_count, lexical_len, index_text, content
          FROM rag.chunks WHERE document_id = %s ORDER BY ordinal""", doc)
    assert chunks
    markdown = sql(database, "SELECT markdown FROM rag.extracted_documents WHERE version_id = %s",
                   ver)[0][0]
    for c in chunks:
        assert (c[0], c[1], c[2]) == (ws, doc, ver)
        assert 0 <= c[6] < c[7] <= len(markdown)
        assert c[8] == "vi"
        assert c[9:13] == ("local", "fake/bge-m3", 1024, "test-rev")
        assert c[15].startswith("Quy trình mua hàng")
    assert [c[3] for c in chunks] == list(range(len(chunks)))
    assert {c[4] for c in chunks} <= {"SECTION", "PROCEDURE_STEP", "TABLE"}
    steps = [c for c in chunks if c[4] == "PROCEDURE_STEP"]
    assert len(steps) == 2 and all(c[5][-1] == "3. Nội dung" for c in steps)

    terms = dict(sql(database, "SELECT t.term, sum(t.tf) FROM rag.chunk_terms t "
                               "JOIN rag.chunks c ON c.id = t.chunk_id WHERE c.document_id = %s "
                               "GROUP BY t.term", doc))
    assert terms["mua_hàng"] >= 1 and terms["~mua_hang"] == terms["mua_hàng"]

    ext = sql(database, """SELECT workspace_id, document_id, normalizer_version, language,
                                  doc_family, extractor, warnings, extracted_meta, page_index
                             FROM rag.extracted_documents WHERE version_id = %s""", ver)[0]
    assert ext[:2] == (ws, doc) and ext[3:5] == ("vi", "ISO_PROCEDURE")
    assert ext[5].startswith("markdown-it-py") and ext[8] is None
    assert sql(database, "SELECT active_version_id, title FROM rag.document_access "
                         "WHERE document_id = %s", doc) == [(ver, "Quy trình mua hàng")]

    events = status_events(database, doc)
    assert [e["status"] for e in events] == ["PROCESSING", "READY"]
    ready = events[1]
    assert ready["attempt"] == 0 and ready["chunkCount"] == len(chunks)
    assert ready["embedding"] == {"provider": "local", "model": "fake/bge-m3",
                                  "revision": "test-rev", "dim": 1024}
    assert ready["detectedLanguage"] == "vi" and isinstance(ready["warningCodes"], list)
    assert set(ready["extracted"]) >= {"docCode", "revisionLabel", "effectiveDate", "approvedBy"}
    assert len(embedder.embedded) == len({c[15] for c in chunks})
    cached = sql(database, "SELECT count(*) FROM rag.embedding_cache WHERE model = %s",
                 "fake/bge-m3")[0][0]
    assert cached >= len({c[15] for c in chunks})


async def test_new_version_reuses_cache_and_replaces_old_chunks(client, database, deps, store,
                                                                embedder) -> None:
    ws, doc, v1, v2 = uuid4(), uuid4(), uuid4(), uuid4()
    for ver, no in ((v1, 1), (v2, 2)):
        body = ingest_body(ws, doc, ver, version_no=no)
        store.objects[body["objectKey"]] = SOP_MD.encode("utf-8")
        await post(client, body)
        embedder.embedded.clear()
        assert await drain(deps, 600, None) == 1
    assert embedder.embedded == []  # same index_text, same model: everything from the cache
    assert {r[0] for r in sql(database, "SELECT version_id FROM rag.chunks WHERE document_id = %s",
                              doc)} == {v2}
    assert sql(database, "SELECT active_version_id FROM rag.document_access "
                         "WHERE document_id = %s", doc) == [(v2,)]


async def test_older_version_finishing_late_is_cancelled(client, database, deps, store) -> None:
    ws, doc, v1, v2 = uuid4(), uuid4(), uuid4(), uuid4()
    b2 = ingest_body(ws, doc, v2, version_no=2)
    store.objects[b2["objectKey"]] = SOP_MD.encode("utf-8")
    await post(client, b2)
    await drain(deps, 600, None)
    b1 = ingest_body(ws, doc, v1, version_no=1)
    store.objects[b1["objectKey"]] = SOP_MD.encode("utf-8")
    await post(client, b1)
    await drain(deps, 600, None)
    assert job_row(database, v1)["status"] == "CANCELLED"
    assert sql(database, "SELECT active_version_id FROM rag.document_access "
                         "WHERE document_id = %s", doc) == [(v2,)]
    assert sql(database, "SELECT count(*) FROM rag.extracted_documents WHERE version_id = %s",
               v1) == [(0,)]


async def test_deleted_document_cancels_and_rolls_back(client, database, deps, store) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    body = ingest_body(ws, doc, ver)
    store.objects[body["objectKey"]] = SOP_MD.encode("utf-8")
    await post(client, body)
    sql(database, "UPDATE rag.document_access SET deleted_at = now() WHERE document_id = %s", doc)
    await drain(deps, 600, None)
    assert job_row(database, ver)["status"] == "CANCELLED"
    assert sql(database, "SELECT count(*) FROM rag.chunks WHERE document_id = %s", doc) == [(0,)]
    assert sql(database, "SELECT count(*) FROM rag.extracted_documents WHERE version_id = %s",
               ver) == [(0,)]
    assert [e["status"] for e in status_events(database, doc)] == ["PROCESSING"]


# -- failures and retries (§5.1, §8) ---------------------------------------------------------------

async def test_deterministic_failure_and_retry_branches(client, database, deps, store) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    body = ingest_body(ws, doc, ver)
    store.objects[body["objectKey"]] = "Quy trình".encode("utf-16")  # not UTF-8
    await post(client, body)
    assert await drain(deps, 600, None) == 1
    job = job_row(database, ver)
    assert (job["status"], job["failure_code"], job["attempts"]) == (
        "FAILED", "INVALID_ENCODING", 1)
    failed = [e for e in status_events(database, doc) if e["status"] == "FAILED"]
    assert len(failed) == 1 and failed[0]["failureCode"] == "INVALID_ENCODING"
    assert failed[0]["failureMessage"].startswith("Tệp Markdown phải")

    # Same attempt again: no new job.
    assert (await post(client, ingest_body(ws, doc, ver))).json() == {"queued": False}
    assert await drain(deps, 600, None) == 0

    # Larger attempt on a FAILED job: back to the queue, runs exactly once.
    store.objects[body["objectKey"]] = SOP_MD.encode("utf-8")
    assert (await post(client, ingest_body(ws, doc, ver, attempt=1))).json() == {"queued": True}
    assert await drain(deps, 600, None) == 1
    assert await drain(deps, 600, None) == 0
    job = job_row(database, ver)
    assert (job["status"], job["failure_code"], job["request_attempt"]) == ("DONE", None, 1)
    ready = status_events(database, doc)[-1]
    assert ready["status"] == "READY" and ready["attempt"] == 1

    # Larger attempt on a DONE job: untouched.
    assert (await post(client, ingest_body(ws, doc, ver, attempt=2))).json() == {"queued": False}
    assert job_row(database, ver)["status"] == "DONE"


async def test_transient_failure_retries_without_failed_callback(client, database, deps) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    await post(client, ingest_body(ws, doc, ver))  # object never uploaded: OBJECT_NOT_FOUND
    deps.backoff_base_seconds = 3600
    async with system_tx(deps.engine) as conn:
        job = await jobs.claim(conn, 600)
    assert await handle_job(job, deps) == "QUEUED"
    row = job_row(database, ver)
    assert (row["status"], row["failure_code"], row["attempts"]) == (
        "QUEUED", "OBJECT_NOT_FOUND", 1)
    assert sql(database, "SELECT run_after > now() + interval '50 minutes' FROM "
                         "rag.ingestion_jobs WHERE version_id = %s", ver) == [(True,)]
    assert [e["status"] for e in status_events(database, doc)] == ["PROCESSING"]
    assert await drain(deps, 600, None) == 0  # backoff not over yet

    # Exhaust the attempts: FAILED once, with the last code.
    sql(database, "UPDATE rag.ingestion_jobs SET run_after = now() WHERE version_id = %s", ver)
    deps.backoff_base_seconds = 0
    assert await drain(deps, 600, None) == 2
    row = job_row(database, ver)
    assert (row["status"], row["failure_code"], row["attempts"]) == (
        "FAILED", "OBJECT_NOT_FOUND", 3)
    assert [e["status"] for e in status_events(database, doc)] == ["PROCESSING", "FAILED"]


async def test_embedding_error_is_transient(client, database, deps, store, embedder) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    body = ingest_body(ws, doc, ver)
    store.objects[body["objectKey"]] = SOP_MD.replace("mua hàng", "mua sắm").encode("utf-8")
    await post(client, body)
    embedder.fail = True
    deps.max_attempts = 1
    assert await drain(deps, 600, None) == 1
    row = job_row(database, ver)
    assert (row["status"], row["failure_code"]) == ("FAILED", "EMBEDDING_ERROR")


async def test_expired_lease_is_reclaimed_then_retry_exhausted(client, database, deps) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    await post(client, ingest_body(ws, doc, ver))
    deps.max_attempts = 1
    async with system_tx(deps.engine) as conn:
        first = await jobs.claim(conn, 0)  # worker "dies": lease ends immediately
    assert first is not None and first.attempts == 1
    async with system_tx(deps.engine) as conn:
        again = await jobs.claim(conn, 600)
    assert again is not None and again.id == first.id and again.attempts == 2
    assert await handle_job(again, deps) == "FAILED"
    row = job_row(database, ver)
    assert (row["status"], row["failure_code"]) == ("FAILED", "RETRY_EXHAUSTED")
    assert status_events(database, doc)[-1]["failureCode"] == "RETRY_EXHAUSTED"


# -- tenant isolation ---------------------------------------------------------------------------

async def test_rls_hides_rows_without_or_with_another_workspace(client, deps, store) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    body = ingest_body(ws, doc, ver)
    store.objects[body["objectKey"]] = SOP_MD.encode("utf-8")
    await post(client, body)
    await drain(deps, 600, None)
    tables = ["chunks", "chunk_terms", "extracted_documents", "document_access",
              "ingestion_jobs", "outbox_events"]
    async with deps.engine.begin() as conn:  # no app.workspace_id at all
        for t in tables:
            assert (await conn.execute(text(f"SELECT count(*) FROM rag.{t}"))).scalar() == 0
    async with tenant_tx(deps.engine, uuid4()) as conn:
        for t in tables:
            assert (await conn.execute(text(f"SELECT count(*) FROM rag.{t}"))).scalar() == 0
    async with tenant_tx(deps.engine, ws) as conn:
        n = (await conn.execute(text("SELECT count(*) FROM rag.chunks"))).scalar()
        assert n > 0
        with pytest.raises(Exception):  # noqa: B017 - RLS WITH CHECK violation
            await conn.execute(text(
                "INSERT INTO rag.document_access (workspace_id, document_id, visibility, "
                "access_revision, title) VALUES (:w, :d, 'WORKSPACE', 1, 't')"),
                {"w": uuid4(), "d": uuid4()})


async def test_pooled_connection_does_not_keep_workspace(deps) -> None:
    ws = uuid4()
    async with tenant_tx(deps.engine, ws) as conn:
        assert (await conn.execute(text("SELECT rag.current_workspace()"))).scalar() == ws
    async with deps.engine.begin() as conn:
        assert (await conn.execute(text("SELECT rag.current_workspace()"))).scalar() is None


# -- outbox dispatcher --------------------------------------------------------------------------

async def test_outbox_delivery_rules(client, database, deps, store) -> None:
    ws, doc, ver = uuid4(), uuid4(), uuid4()
    body = ingest_body(ws, doc, ver)
    store.objects[body["objectKey"]] = SOP_MD.encode("utf-8")
    await post(client, body)
    await drain(deps, 600, None)
    seen: list[httpx.Request] = []
    replies = {"PROCESSING": 200, "READY": 409}

    def handler(request: httpx.Request) -> httpx.Response:
        if not request.url.path.startswith(f"/internal/documents/{doc}/"):
            return httpx.Response(503)  # events of other tests stay PENDING
        seen.append(request)
        return httpx.Response(replies[json.loads(request.content)["status"]])

    async with httpx.AsyncClient(base_url="http://core",
                                 transport=httpx.MockTransport(handler)) as http:
        await OutboxDispatcher(deps.engine, http, TOKEN).dispatch_due()
    assert {r.headers["X-Internal-Token"] for r in seen} == {TOKEN}
    assert all(r.url.path == f"/internal/documents/{doc}/versions/{ver}/status" for r in seen)
    assert all(r.method == "PATCH" and "versionId" not in json.loads(r.content) for r in seen)
    rows = dict(sql(database, "SELECT payload->>'status', status FROM rag.outbox_events "
                              "WHERE aggregate_id = %s", doc))
    assert rows == {"PROCESSING": "DELIVERED", "READY": "DEAD"}  # 409 is never retried
    keys = [r.headers["Idempotency-Key"] for r in seen]
    ids = [str(r[0]) for r in sql(database, "SELECT id FROM rag.outbox_events "
                                            "WHERE aggregate_id = %s", doc)]
    assert sorted(keys) == sorted(ids)


async def test_outbox_server_error_is_retried_later(database, deps) -> None:
    ws, doc = uuid4(), uuid4()
    async with tenant_tx(deps.engine, ws) as conn:
        from sopilot_ai.db.repositories import outbox

        await outbox.add(conn, workspace_id=ws, aggregate_id=doc, event_type="VERSION_STATUS",
                         payload={"workspaceId": str(ws), "versionId": str(uuid4()),
                                  "status": "READY", "attempt": 0})
    async with httpx.AsyncClient(base_url="http://core", transport=httpx.MockTransport(
            lambda _r: httpx.Response(500))) as http:
        await OutboxDispatcher(deps.engine, http, TOKEN).dispatch_due()
    row = sql(database, "SELECT status, attempts, next_attempt_at > now(), last_error "
                        "FROM rag.outbox_events WHERE aggregate_id = %s", doc)
    assert row == [("PENDING", 1, True, "HTTP 500")]
