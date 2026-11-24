# ruff: noqa: F811 - imported fixtures are used by name as test arguments
"""FR-19 through the question-answering API: three workspaces, one secret string each.

The scripted LLM repeats, word for word, every source it is given. So if retrieval, the context
assembly or the conversation read ever crossed a workspace line, the other workspace's secret
would appear in a stream, a citation or a stored conversation, and these tests would see it.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx
import pytest
from test_retrieval import (  # noqa: F401
    IDENTITY,
    TOKEN,
    FakeStore,
    bearer,
    body,
    client,
    deps,
    embedder,
    ingest,
    keypair,
    sql,
    store,
)

from fakes import BowEmbedder, ScriptedChain
from sopilot_ai.api.app import create_app
from sopilot_ai.auth.jwt import TokenVerifier
from sopilot_ai.config import Settings
from sopilot_ai.conversations.service import QAService
from sopilot_ai.providers.registry import RetrievalConfig
from sopilot_ai.quota.counters import QuotaCounter
from sopilot_ai.retrieval.access_filter import Principal
from sopilot_ai.retrieval.context import ContextConfig
from sopilot_ai.retrieval.retriever import Retriever
from sopilot_ai.worker import drain

SECRETS = {"alpha": "ALPHA7731", "bravo": "BRAVO4482", "charlie": "CHARLIE9015"}
QUESTION = "mật khẩu kho dữ liệu là gì"
# A question that names every secret: only the asker's own can ever come back.
GREEDY = QUESTION + " " + " ".join(SECRETS.values())
_SOURCE = re.compile(r'<source n="1"[^>]*>\n(.*?)\n</source>', re.DOTALL)


def doc_text(secret: str) -> str:
    return (f"# Kho dữ liệu\n\n## 1. Truy cập\n\nMật khẩu kho dữ liệu là {secret} và chỉ phòng "
            "tài chính được biết mật khẩu này.\n")


def echo_first_source(messages) -> list[str]:  # noqa: ANN001
    """What a model that copies its context would write."""
    found = _SOURCE.search(messages[0]["content"])
    return [(found.group(1) if found else "Không có nguồn") + " [1]"]


@dataclass
class Tenant:
    name: str
    secret: str
    principal: Principal
    doc: UUID
    ver: UUID


@pytest.fixture
async def tenants(client, store, deps) -> dict[str, Tenant]:  # noqa: ANN001
    out: dict[str, Tenant] = {}
    for name, secret in SECRETS.items():
        ws, doc, ver = uuid4(), uuid4(), uuid4()
        await ingest(client, store, body(ws, doc, ver, f"Kho dữ liệu {name}"), doc_text(secret))
        out[name] = Tenant(name, secret, Principal(uuid4(), ws, "OWNER"), doc, ver)
    assert await drain(deps, 600, None) == len(SECRETS)
    return out


@pytest.fixture
async def api(engine, keypair) -> AsyncIterator[httpx.AsyncClient]:  # noqa: ANN001
    service = QAService(
        engine, Retriever(BowEmbedder(), RetrievalConfig(thresholds={"hybrid": 0.0})),
        ScriptedChain(echo_first_source), ScriptedChain(), context=ContextConfig(),
        quota=QuotaCounter(engine))
    settings = Settings.model_validate({"SOPILOT_DB_URL": "postgresql://unused",
                                        "SOPILOT_INTERNAL_TOKEN": TOKEN})
    app = create_app(settings, engine, embedding_identity=IDENTITY, qa_service=service,
                     token_verifier=TokenVerifier(key_for=lambda _t: keypair[1]))
    app.state.engine = engine
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://ai") as c:
        yield c


def others(tenants: dict[str, Tenant], me: Tenant) -> list[Tenant]:
    return [t for t in tenants.values() if t.name != me.name]


async def ask(api, keypair, who: Tenant, content: str,  # noqa: ANN001
              conversation: str = "new") -> httpx.Response:
    return await api.post(f"/ai/v1/conversations/{conversation}/messages",
                          json={"content": content}, headers=bearer(keypair, who.principal))


def conversation_id(resp: httpx.Response) -> str:
    meta = next(ln for ln in resp.text.splitlines() if ln.startswith("data: "))
    return json.loads(meta.removeprefix("data: "))["conversationId"]


async def test_an_answer_only_ever_contains_the_askers_own_secret(
        api, keypair, tenants) -> None:  # noqa: ANN001
    for me in tenants.values():
        for question in (QUESTION, GREEDY):
            resp = await ask(api, keypair, me, question)
            assert resp.status_code == 200
            assert me.secret in resp.text  # the model was given the asker's own document
            for other in others(tenants, me):
                assert other.secret not in resp.text
                assert str(other.doc) not in resp.text and str(other.ver) not in resp.text


async def test_citations_and_stored_turns_point_only_into_the_askers_workspace(
        api, keypair, tenants, database) -> None:  # noqa: ANN001
    for me in tenants.values():
        await ask(api, keypair, me, GREEDY)
    for t in tenants.values():  # the database is shared by the tests of a run: look per workspace
        cited = sql(database, "SELECT DISTINCT document_id FROM rag.message_citations "
                              "WHERE workspace_id = %s", t.principal.workspace_id)
        assert cited == [(t.doc,)]

    # No row of one workspace is linked to a parent row of another one.
    crossed = sql(database,
                  "SELECT count(*) FROM rag.messages m JOIN rag.conversations c "
                  "ON c.id = m.conversation_id WHERE m.workspace_id <> c.workspace_id "
                  "OR m.user_id <> c.user_id")[0][0]
    assert crossed == 0
    leaked = sql(database,
                 "SELECT count(*) FROM rag.retrieval_results r JOIN rag.chunks k "
                 "ON k.id = r.chunk_id WHERE r.workspace_id <> k.workspace_id")[0][0]
    assert leaked == 0
    for t in tenants.values():
        # Answers only: the question itself names every secret on purpose.
        for (content,) in sql(database, "SELECT content FROM rag.messages "
                                        "WHERE workspace_id = %s AND role = 'ASSISTANT'",
                              t.principal.workspace_id):
            for other in others(tenants, t):
                assert other.secret not in content


async def test_another_workspaces_conversation_is_a_404_for_every_operation(
        api, keypair, tenants) -> None:  # noqa: ANN001
    ids = {t.name: conversation_id(await ask(api, keypair, t, QUESTION))
           for t in tenants.values()}
    for me in tenants.values():
        headers = bearer(keypair, me.principal)
        for other in others(tenants, me):
            cid = ids[other.name]
            assert (await api.get(f"/ai/v1/conversations/{cid}", headers=headers)
                    ).status_code == 404
            assert (await ask(api, keypair, me, QUESTION, cid)).status_code == 404
            assert (await api.patch(f"/ai/v1/conversations/{cid}", json={"title": "x"},
                                    headers=headers)).status_code == 404
            assert (await api.delete(f"/ai/v1/conversations/{cid}", headers=headers)
                    ).status_code == 404
        listed = (await api.get("/ai/v1/conversations", headers=headers)).json()
        assert [c["id"] for c in listed] == [ids[me.name]]
        mine = (await api.get(f"/ai/v1/conversations/{ids[me.name]}", headers=headers)).text
        assert me.secret in mine
        assert all(o.secret not in mine for o in others(tenants, me))


async def test_a_teammate_in_the_same_workspace_cannot_read_the_conversation_either(
        api, keypair, tenants) -> None:  # noqa: ANN001
    me = tenants["alpha"]
    cid = conversation_id(await ask(api, keypair, me, QUESTION))
    teammate = Principal(uuid4(), me.principal.workspace_id, "OWNER")
    headers = bearer(keypair, teammate)
    assert (await api.get(f"/ai/v1/conversations/{cid}", headers=headers)).status_code == 404
    assert (await api.get("/ai/v1/conversations", headers=headers)).json() == []
