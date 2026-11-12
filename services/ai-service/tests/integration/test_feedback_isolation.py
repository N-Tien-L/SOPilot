# ruff: noqa: F811 - imported fixtures are used by name as test arguments
"""FR-16/FR-17 through the API, FR-19 across workspaces (TECH-V2-ai-service §7.6, V2-13).

Three workspaces (A, B, C), each with a secret string in its questions. Checks: a MEMBER cannot read
the gap list; the list holds only the gap criteria (never OUT_OF_SCOPE, TEMPLATE or INPUT_INVALID);
questions are PII-masked; no asker identity; feedback is accepted only from the conversation's
owner and only on an ASSISTANT message; a resolve is recorded once; no other workspace sees the
feedback, comments, questions or gaps, and the feedback subqueries count only their own workspace.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from test_retrieval import bearer, client, keypair, sql  # noqa: F401

from sopilot_ai.conversations import repository as conv_repo
from sopilot_ai.conversations.repository import TurnRecord
from sopilot_ai.db.engine import tenant_tx
from sopilot_ai.retrieval.access_filter import Principal

GAP_SECRET_A = "GAPSECRET-A"
GAP_SECRET_B = "GAPSECRET-B"
GAP_SECRET_C = "GAPSECRET-C"


async def seed_turn(engine, asker: Principal, *, question: str, outcome: str,
                    refusal_reason: str | None = None, checks: dict | None = None,
                    answer: str = "answer") -> tuple[UUID, UUID]:
    """One conversation with one question and answer; returns (assistant_id, conversation_id)."""
    now = datetime.now(UTC)
    rec = TurnRecord(
        conversation_id=uuid4(), new_conversation=True, title="t",
        user_message_id=uuid4(), assistant_message_id=uuid4(), question=question, lang="vi",
        answer=answer, outcome=outcome, user_created=now,
        assistant_created=now + timedelta(milliseconds=5), refusal_reason=refusal_reason,
        checks=checks or {})
    async with tenant_tx(engine, asker.workspace_id, asker.user_id) as conn:
        await conv_repo.save_turn(conn, asker, rec)
    return rec.assistant_message_id, rec.conversation_id


@pytest.fixture
async def world(engine):  # noqa: ANN001, ANN201
    ws_a, ws_b, ws_c = uuid4(), uuid4(), uuid4()
    asker = Principal(uuid4(), ws_a, "MEMBER")
    other_member = Principal(uuid4(), ws_a, "MEMBER")
    admin = Principal(uuid4(), ws_a, "ADMIN")
    owner_b = Principal(uuid4(), ws_b, "OWNER")
    asker_c = Principal(uuid4(), ws_c, "MEMBER")
    admin_c = Principal(uuid4(), ws_c, "ADMIN")
    ids: dict[str, UUID] = {}
    ids["gap_refusal"], _ = await seed_turn(
        engine, asker, question=f"Mật khẩu kho {GAP_SECRET_A} liên hệ 0912345678, a@b.com?",
        outcome="REFUSED_NO_EVIDENCE", refusal_reason="NO_EVIDENCE")
    ids["gap_nocite"], _ = await seed_turn(
        engine, asker, question="Quy trình X?", outcome="ANSWERED", checks={"citationCount": 0})
    ids["downvoted_later"], _ = await seed_turn(
        engine, asker, question="Quy trình Y?", outcome="ANSWERED", checks={"citationCount": 2})
    ids["out_of_scope"], _ = await seed_turn(
        engine, asker, question="Thời tiết?", outcome="REFUSED_NO_EVIDENCE",
        refusal_reason="OUT_OF_SCOPE")
    ids["template"], _ = await seed_turn(engine, asker, question="Chào", outcome="TEMPLATE")
    ids["answered"], _ = await seed_turn(
        engine, asker, question="Quy trình Z?", outcome="ANSWERED", checks={"citationCount": 1})
    ids["b_gap"], _ = await seed_turn(
        engine, owner_b, question=f"Bí mật {GAP_SECRET_B}?", outcome="REFUSED_NO_EVIDENCE",
        refusal_reason="NO_EVIDENCE")
    ids["c_gap"], _ = await seed_turn(
        engine, asker_c, question=f"Quy trình {GAP_SECRET_C} ở đâu?", outcome="REFUSED_NO_EVIDENCE",
        refusal_reason="NO_EVIDENCE")
    ids["c_answered"], _ = await seed_turn(
        engine, asker_c, question="Quy trình C?", outcome="ANSWERED", checks={"citationCount": 1})
    return {"ws_a": ws_a, "asker": asker, "other": other_member, "admin": admin,
            "owner_b": owner_b, "asker_c": asker_c, "admin_c": admin_c, "ids": ids}


def headers(keypair, p: Principal) -> dict[str, str]:  # noqa: ANN001
    return bearer(keypair, p)


async def test_member_cannot_read_gap_list(client: httpx.AsyncClient, keypair, world) -> None:  # noqa: ANN001
    r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["asker"]))
    assert r.status_code == 403


async def test_list_holds_only_gap_criteria(client, keypair, world) -> None:  # noqa: ANN001
    r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["admin"]))
    assert r.status_code == 200
    got = {item["messageId"] for item in r.json()}
    ids = world["ids"]
    assert got == {str(ids["gap_refusal"]), str(ids["gap_nocite"])}


async def test_questions_are_masked_and_no_asker_identity(client, keypair, world) -> None:  # noqa: ANN001
    r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["admin"]))
    raw = r.text
    assert "a@b.com" not in raw and "0912345678" not in raw
    assert "[EMAIL]" in raw and "[PHONE]" in raw
    assert str(world["asker"].user_id) not in raw
    assert "userId" not in raw and "user_id" not in raw


async def test_other_workspace_gap_never_visible(client, keypair, world) -> None:  # noqa: ANN001
    r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["admin"]))
    assert GAP_SECRET_B not in r.text and GAP_SECRET_C not in r.text
    r_b = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["owner_b"]))
    assert GAP_SECRET_A not in r_b.text and GAP_SECRET_C not in r_b.text
    assert [i["messageId"] for i in r_b.json()] == [str(world["ids"]["b_gap"])]
    r_c = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["admin_c"]))
    assert GAP_SECRET_A not in r_c.text and GAP_SECRET_B not in r_c.text
    assert [i["messageId"] for i in r_c.json()] == [str(world["ids"]["c_gap"])]


async def test_three_workspaces_see_only_their_own_gap_lists(
        client, keypair, world) -> None:  # noqa: ANN001
    # Each workspace's open list holds exactly its own gap; the other two are absent.
    expected = {"admin": {world["ids"]["gap_refusal"], world["ids"]["gap_nocite"]},
                "owner_b": {world["ids"]["b_gap"]},
                "admin_c": {world["ids"]["c_gap"]}}
    for who, ids in expected.items():
        r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world[who]))
        assert r.status_code == 200, who
        assert {i["messageId"] for i in r.json()} == {str(x) for x in ids}, who


async def test_feedback_and_comments_stay_in_their_workspace(
        client, keypair, world) -> None:  # noqa: ANN001
    # Workspace C leaves a comment on its own answer; A and B never see it.
    mid = world["ids"]["c_gap"]
    r = await client.put(f"/ai/v1/messages/{mid}/feedback", json={"vote": -1, "comment": "C-NOTE"},
                         headers=headers(keypair, world["asker_c"]))
    assert r.status_code == 204
    for who in ("admin", "owner_b"):
        r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world[who]))
        assert "C-NOTE" not in r.text
    r_c = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["admin_c"]))
    gap_c = next(i for i in r_c.json() if i["messageId"] == str(mid))
    assert gap_c["downvotes"] == 1 and gap_c["comments"] == [{"vote": -1, "comment": "C-NOTE"}]


async def test_feedback_on_other_workspace_answer_is_404_for_every_workspace(
        client, keypair, world) -> None:  # noqa: ANN001
    body = {"vote": -1, "comment": "xen vào"}
    a, c = world["ids"]["answered"], world["ids"]["c_answered"]
    for who, mid in (("owner_b", a), ("asker_c", a), ("asker", c), ("owner_b", c)):
        r = await client.put(f"/ai/v1/messages/{mid}/feedback", json=body,
                             headers=headers(keypair, world[who]))
        assert r.status_code == 404, (who, mid)


async def test_gap_resolve_is_404_across_all_three_workspaces(
        client, keypair, world) -> None:  # noqa: ANN001
    for who, mid in (("admin_c", world["ids"]["gap_refusal"]),
                     ("admin", world["ids"]["c_gap"]),
                     ("owner_b", world["ids"]["c_gap"]),
                     ("admin_c", world["ids"]["b_gap"])):
        r = await client.post(f"/ai/v1/knowledge-gaps/{mid}/resolve", json={},
                              headers=headers(keypair, world[who]))
        assert r.status_code == 404, (who, mid)


async def test_feedback_upsert_refreshes_updated_at(client, keypair, world, database) -> None:  # noqa: ANN001
    # rag.message_feedback has BEFORE UPDATE trigger trg_message_feedback_updated (V003), which
    # fires on the ON CONFLICT DO UPDATE path, so a changed vote moves updated_at forward.
    mid = world["ids"]["c_answered"]
    url = f"/ai/v1/messages/{mid}/feedback"
    hdr = headers(keypair, world["asker_c"])
    assert (await client.put(url, json={"vote": -1}, headers=hdr)).status_code == 204
    (first,) = sql(database, "SELECT updated_at FROM rag.message_feedback WHERE message_id = %s",
                   mid)
    assert (await client.put(url, json={"vote": 1}, headers=hdr)).status_code == 204
    (second,) = sql(database, "SELECT updated_at FROM rag.message_feedback WHERE message_id = %s",
                    mid)
    assert second[0] > first[0]
    assert sql(database, "SELECT vote FROM rag.message_feedback WHERE message_id = %s", mid) == [
        (1,)]


async def test_feedback_row_of_another_workspace_is_not_counted(
        client, keypair, world, database) -> None:  # noqa: ANN001
    # Defence in depth: a row tagged with workspace C on a workspace-A message must not count in
    # A's gap list. RLS already hides it under A's tenant; the explicit workspace_id filter is
    # the second layer that this test exercises.
    gid = world["ids"]["gap_nocite"]
    sql(database, "INSERT INTO rag.message_feedback (workspace_id, message_id, user_id, vote) "
                  "VALUES (%s, %s, %s, -1)", world["asker_c"].workspace_id, gid,
        world["asker_c"].user_id)
    r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["admin"]))
    row = next(i for i in r.json() if i["messageId"] == str(gid))
    assert row["downvotes"] == 0


async def test_feedback_only_by_conversation_owner_on_assistant_message(
        client, keypair, world, database) -> None:  # noqa: ANN001
    mid = world["ids"]["answered"]
    url = f"/ai/v1/messages/{mid}/feedback"
    r = await client.put(url, json={"vote": -1, "comment": "không đúng"},
                         headers=headers(keypair, world["other"]))
    assert r.status_code == 404
    r = await client.put(url, json={"vote": -1}, headers=headers(keypair, world["owner_b"]))
    assert r.status_code == 404
    r = await client.put(url, json={"vote": -1, "comment": "không đúng"},
                         headers=headers(keypair, world["asker"]))
    assert r.status_code == 204
    r = await client.put(url, json={"vote": 1, "comment": "  "},
                         headers=headers(keypair, world["asker"]))
    assert r.status_code == 204
    rows = sql(database, "SELECT vote, comment FROM rag.message_feedback WHERE message_id = %s",
               mid)
    assert rows == [(1, None)]  # one vote per user and answer; the later vote replaces it


async def test_user_message_and_bad_vote_are_rejected(client, keypair, world) -> None:  # noqa: ANN001
    r = await client.put(f"/ai/v1/messages/{uuid4()}/feedback", json={"vote": 1},
                         headers=headers(keypair, world["asker"]))
    assert r.status_code == 404
    r = await client.put(f"/ai/v1/messages/{world['ids']['answered']}/feedback",
                         json={"vote": 0}, headers=headers(keypair, world["asker"]))
    assert r.status_code == 422


async def test_downvote_adds_gap_but_scope_refusal_stays_out(
        client, keypair, world) -> None:  # noqa: ANN001
    await client.put(f"/ai/v1/messages/{world['ids']['out_of_scope']}/feedback",
                     json={"vote": -1}, headers=headers(keypair, world["asker"]))
    await client.put(f"/ai/v1/messages/{world['ids']['answered']}/feedback",
                     json={"vote": -1}, headers=headers(keypair, world["asker"]))
    r = await client.get("/ai/v1/knowledge-gaps", headers=headers(keypair, world["admin"]))
    got = {i["messageId"] for i in r.json()}
    assert str(world["ids"]["out_of_scope"]) not in got
    assert str(world["ids"]["answered"]) in got


async def test_resolve_moves_gap_to_resolved_once(client, keypair, world) -> None:  # noqa: ANN001
    gid = world["ids"]["gap_refusal"]
    hdr = headers(keypair, world["admin"])
    r = await client.post(f"/ai/v1/knowledge-gaps/{gid}/resolve", json={"note": "đã thêm SOP"},
                          headers=hdr)
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    r = await client.post(f"/ai/v1/knowledge-gaps/{gid}/resolve", json={}, headers=hdr)
    assert r.status_code == 200  # idempotent
    open_ids = {i["messageId"] for i in
                (await client.get("/ai/v1/knowledge-gaps", headers=hdr)).json()}
    assert str(gid) not in open_ids
    resolved = (await client.get("/ai/v1/knowledge-gaps?status=resolved", headers=hdr)).json()
    assert [i["messageId"] for i in resolved] == [str(gid)]
    assert resolved[0]["resolutionNote"] == "đã thêm SOP"


async def test_resolve_rules(client, keypair, world) -> None:  # noqa: ANN001
    r = await client.post(f"/ai/v1/knowledge-gaps/{world['ids']['answered']}/resolve", json={},
                          headers=headers(keypair, world["admin"]))
    assert r.status_code == 404  # not a gap
    r = await client.post(f"/ai/v1/knowledge-gaps/{world['ids']['gap_nocite']}/resolve", json={},
                          headers=headers(keypair, world["asker"]))
    assert r.status_code == 403  # a member cannot resolve
    r = await client.post(f"/ai/v1/knowledge-gaps/{world['ids']['b_gap']}/resolve", json={},
                          headers=headers(keypair, world["admin"]))
    assert r.status_code == 404  # another workspace's gap
