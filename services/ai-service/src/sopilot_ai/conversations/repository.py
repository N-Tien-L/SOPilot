"""SQL of conversations, messages and their evidence (TECH-V2-ai-service §3.4, §7.5).

Every function takes a connection from ``tenant_tx`` and filters ``workspace_id = :wid`` (and the
owner, ``user_id = :uid``) next to RLS. A conversation that is not the caller's is "not found":
there is no way to tell it from one that does not exist (FR-19). Whether a stored answer may still
be shown is decided against the current access filter (``cited_access_cte``), never against a
copy taken when the answer was written.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.db.repositories import retrieval_results
from sopilot_ai.qa.citations import Citation
from sopilot_ai.qa.pipeline import GuardEvent
from sopilot_ai.retrieval.access_filter import Principal, access_params, cited_access_cte
from sopilot_ai.retrieval.retriever import RetrievalResult

REASON_REVOKED = "ACCESS_REVOKED"
REASON_DELETED = "DOCUMENT_DELETED"

_NEW_CONVERSATION = text("""
INSERT INTO rag.conversations (id, workspace_id, user_id, title)
VALUES (:id, :wid, :uid, :title)
""")
_TOUCH_CONVERSATION = text("""
UPDATE rag.conversations SET updated_at = now()
 WHERE id = :id AND workspace_id = :wid AND user_id = :uid
""")
_GET_CONVERSATION = text("""
SELECT id, title, created_at, updated_at FROM rag.conversations
 WHERE id = :id AND workspace_id = :wid AND user_id = :uid AND deleted_at IS NULL
""")
_LIST = text("""
SELECT id, title, created_at, updated_at FROM rag.conversations
 WHERE workspace_id = :wid AND user_id = :uid AND deleted_at IS NULL
 ORDER BY updated_at DESC, id
 LIMIT :limit OFFSET :offset
""")
_RENAME = text("""
UPDATE rag.conversations SET title = :title
 WHERE id = :id AND workspace_id = :wid AND user_id = :uid AND deleted_at IS NULL
RETURNING id
""")
_DELETE = text("""
UPDATE rag.conversations SET deleted_at = now()
 WHERE id = :id AND workspace_id = :wid AND user_id = :uid AND deleted_at IS NULL
RETURNING id
""")

_INSERT_MESSAGE = text("""
INSERT INTO rag.messages (id, workspace_id, conversation_id, user_id, role, content,
    standalone_query, outcome, refusal_reason, route, rewrite_status, checks, lang,
    retrieval_mode, gate_score, threshold, model, prompt_version, tokens_in, tokens_out,
    latency_ms, context_sources, created_at)
VALUES (:id, :wid, :cid, :uid, :role, :content, :standalone, :outcome, :reason,
    CAST(:route AS jsonb), :rewrite_status, CAST(:checks AS jsonb), :lang, :mode, :gate,
    :threshold, :model, :prompt_version, NULL, NULL, CAST(:latency AS jsonb),
    CAST(:sources AS jsonb), :created_at)
""")
_INSERT_CITATION = text("""
INSERT INTO rag.message_citations (workspace_id, message_id, n, chunk_id, document_id, version_id,
                                   page_start, char_start, char_end, snippet)
VALUES (:wid, :msg, :n, :chunk, :doc, :ver, :page, :cs, :ce, :snippet)
""")
_INSERT_GUARD = text("""
INSERT INTO rag.guard_events (id, workspace_id, message_id, user_id, layer, rule_id)
VALUES (:id, :wid, :msg, :uid, :layer, :rule)
""")

_RECENT = text("""
SELECT id, role, content, outcome, created_at FROM rag.messages
 WHERE conversation_id = :cid AND workspace_id = :wid AND user_id = :uid
 ORDER BY created_at DESC, role ASC
 LIMIT :limit
""")
_MESSAGES = text("""
SELECT id, role, content, outcome, refusal_reason, created_at FROM rag.messages
 WHERE conversation_id = :cid AND workspace_id = :wid AND user_id = :uid
 ORDER BY created_at, role DESC
""")

_HIDDEN = text(f"""
WITH {cited_access_cte()}
SELECT mc.message_id,
       bool_or(ca.document_id IS NULL OR ca.deleted) AS deleted
  FROM rag.message_citations mc
  LEFT JOIN cited_access ca ON ca.document_id = mc.document_id
 WHERE mc.workspace_id = :wid AND mc.message_id = ANY (CAST(:ids AS uuid[]))
 GROUP BY mc.message_id
HAVING bool_or(ca.document_id IS NULL OR NOT ca.readable)
""")
_CITATIONS = text(f"""
WITH {cited_access_cte()}
SELECT mc.message_id, mc.n, mc.document_id, mc.version_id, mc.page_start, mc.char_start,
       mc.char_end, mc.snippet, ca.title, (ca.active_version_id = mc.version_id) AS current
  FROM rag.message_citations mc
  LEFT JOIN cited_access ca ON ca.document_id = mc.document_id
 WHERE mc.workspace_id = :wid AND mc.message_id = ANY (CAST(:ids AS uuid[]))
 ORDER BY mc.message_id, mc.n
""")


def _json(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, default=str)


@dataclass
class TurnRecord:
    """Everything one question leaves behind. Written in one transaction after the answer."""

    conversation_id: UUID
    new_conversation: bool
    title: str
    user_message_id: UUID
    assistant_message_id: UUID
    question: str  # as the user typed it (messages.content keeps the original, TECH §7.1 step 2)
    lang: str | None
    answer: str
    outcome: str
    user_created: datetime
    assistant_created: datetime
    refusal_reason: str | None = None
    standalone_query: str | None = None
    rewrite_status: str = "NONE"
    route: dict[str, Any] = field(default_factory=dict)
    checks: dict[str, Any] = field(default_factory=dict)
    retrieval_mode: str | None = None
    gate_score: float | None = None
    threshold: float | None = None
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: dict[str, int] = field(default_factory=dict)
    context_sources: list[dict] | None = None
    citations: Sequence[Citation] = ()
    guard_events: Sequence[GuardEvent] = ()
    retrieval: RetrievalResult | None = None


async def get_conversation(conn: AsyncConnection, principal: Principal,
                           conversation_id: UUID) -> Any | None:
    return (await conn.execute(_GET_CONVERSATION, {
        "id": conversation_id, "wid": principal.workspace_id, "uid": principal.user_id})).first()


async def save_turn(conn: AsyncConnection, principal: Principal, rec: TurnRecord) -> None:
    wid, uid = principal.workspace_id, principal.user_id
    if rec.new_conversation:
        await conn.execute(_NEW_CONVERSATION, {"id": rec.conversation_id, "wid": wid, "uid": uid,
                                               "title": rec.title})
    else:
        await conn.execute(_TOUCH_CONVERSATION, {"id": rec.conversation_id, "wid": wid,
                                                 "uid": uid})
    common = {"cid": rec.conversation_id, "wid": wid, "uid": uid}
    blank = {"standalone": None, "outcome": None, "reason": None, "route": None,
             "rewrite_status": None, "checks": None, "mode": None, "gate": None,
             "threshold": None, "model": None, "prompt_version": None, "latency": None,
             "sources": None}
    await conn.execute(_INSERT_MESSAGE, {
        **common, **blank, "id": rec.user_message_id, "role": "USER", "content": rec.question,
        "lang": rec.lang, "created_at": rec.user_created})
    await conn.execute(_INSERT_MESSAGE, {
        **common, "id": rec.assistant_message_id, "role": "ASSISTANT", "content": rec.answer,
        "standalone": rec.standalone_query, "outcome": rec.outcome, "reason": rec.refusal_reason,
        "route": _json(rec.route), "rewrite_status": rec.rewrite_status,
        "checks": _json(rec.checks), "lang": rec.lang, "mode": rec.retrieval_mode,
        "gate": rec.gate_score, "threshold": rec.threshold, "model": rec.model,
        "prompt_version": rec.prompt_version, "latency": _json(rec.latency_ms),
        "sources": _json(rec.context_sources), "created_at": rec.assistant_created})
    msg = rec.assistant_message_id
    for c in rec.citations:
        await conn.execute(_INSERT_CITATION, {
            "wid": wid, "msg": msg, "n": c.n, "chunk": c.chunk_id, "doc": c.document_id,
            "ver": c.version_id, "page": c.page_start, "cs": c.char_start, "ce": c.char_end,
            "snippet": c.snippet})
    for ev in rec.guard_events:
        await conn.execute(_INSERT_GUARD, {"id": uuid4(), "wid": wid, "msg": msg, "uid": uid,
                                           "layer": ev.layer, "rule": ev.rule_id})
    if rec.retrieval is not None:
        await retrieval_results.save(conn, wid, msg, rec.retrieval)


async def hidden_answers(conn: AsyncConnection, principal: Principal,
                         message_ids: Sequence[UUID]) -> dict[UUID, str]:
    """``message_id -> reason`` for answers with a citation the asker can no longer read.

    One unreadable citation hides the whole answer (TECH §7.5). ``DOCUMENT_DELETED`` when a cited
    document is gone, else ``ACCESS_REVOKED``.
    """
    if not message_ids:
        return {}
    rows = (await conn.execute(_HIDDEN, {
        **access_params(principal), "ids": [str(i) for i in message_ids]})).all()
    return {r.message_id: REASON_DELETED if r.deleted else REASON_REVOKED for r in rows}


async def recent_turns(conn: AsyncConnection, principal: Principal, conversation_id: UUID,
                       limit: int = 3) -> list[tuple[str, str]]:
    """The last ``limit`` answered ``(question, answer)`` pairs, oldest first, for the rewrite.

    Pairs whose answer is hidden (access revoked, document deleted) are left out, so a revoked
    document's text can never come back through the rewrite call. Refusals and templates are not
    history: only ``ANSWERED`` turns carry something to refer back to.
    """
    rows = (await conn.execute(_RECENT, {
        "cid": conversation_id, "wid": principal.workspace_id, "uid": principal.user_id,
        "limit": limit * 4})).all()
    ordered = list(reversed(rows))
    answers = [r.id for r in ordered if r.role == "ASSISTANT" and r.outcome == "ANSWERED"]
    hidden = await hidden_answers(conn, principal, answers)
    pairs: list[tuple[str, str]] = []
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if (prev.role == "USER" and cur.role == "ASSISTANT" and cur.outcome == "ANSWERED"
                and cur.id not in hidden):
            pairs.append((prev.content, cur.content))
    return pairs[-limit:]


async def list_conversations(conn: AsyncConnection, principal: Principal, *, limit: int = 50,
                             offset: int = 0) -> list[Any]:
    return list((await conn.execute(_LIST, {
        "wid": principal.workspace_id, "uid": principal.user_id, "limit": limit,
        "offset": offset})).all())


async def conversation_detail(conn: AsyncConnection, principal: Principal,
                              conversation_id: UUID) -> dict[str, Any] | None:
    """The conversation with its messages and citations, or ``None`` if it is not the caller's.

    An answer with an unreadable citation is replaced by ``{hidden: true, reason}``; the question
    stays (PRD §8.8). A citation to an older version keeps its stored snippet and is marked
    ``isCurrentVersion: false`` (D10).
    """
    conv = await get_conversation(conn, principal, conversation_id)
    if conv is None:
        return None
    msgs = (await conn.execute(_MESSAGES, {
        "cid": conversation_id, "wid": principal.workspace_id, "uid": principal.user_id})).all()
    ids = [m.id for m in msgs if m.role == "ASSISTANT"]
    hidden = await hidden_answers(conn, principal, ids)
    cites: dict[UUID, list[dict[str, Any]]] = {}
    if ids:
        rows = (await conn.execute(_CITATIONS, {
            **access_params(principal), "ids": [str(i) for i in ids]})).all()
        for r in rows:
            cites.setdefault(r.message_id, []).append({
                "n": r.n, "documentId": str(r.document_id), "versionId": str(r.version_id),
                "title": r.title, "page": r.page_start, "charStart": r.char_start,
                "charEnd": r.char_end, "snippet": r.snippet,
                "isCurrentVersion": bool(r.current)})
    out: list[dict[str, Any]] = []
    for m in msgs:
        item: dict[str, Any] = {"id": str(m.id), "role": m.role,
                                "createdAt": m.created_at.isoformat()}
        if m.id in hidden:
            item.update({"hidden": True, "reason": hidden[m.id]})
        else:
            item["content"] = m.content
            if m.role == "ASSISTANT":
                item.update({"outcome": m.outcome, "refusalReason": m.refusal_reason,
                             "citations": cites.get(m.id, [])})
        out.append(item)
    return {"id": str(conv.id), "title": conv.title, "createdAt": conv.created_at.isoformat(),
            "updatedAt": conv.updated_at.isoformat(), "messages": out}


async def rename(conn: AsyncConnection, principal: Principal, conversation_id: UUID,
                 title: str) -> bool:
    row = (await conn.execute(_RENAME, {"id": conversation_id, "wid": principal.workspace_id,
                                        "uid": principal.user_id, "title": title})).first()
    return row is not None


async def soft_delete(conn: AsyncConnection, principal: Principal,
                      conversation_id: UUID) -> bool:
    row = (await conn.execute(_DELETE, {"id": conversation_id, "wid": principal.workspace_id,
                                        "uid": principal.user_id})).first()
    return row is not None
