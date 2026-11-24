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

from sopilot_ai.conversations.trace import strip_document_data, synthesize_legacy_trace
from sopilot_ai.db.repositories import retrieval_results
from sopilot_ai.qa.citations import Citation
from sopilot_ai.qa.pipeline import GuardEvent
from sopilot_ai.retrieval.access_filter import (
    Principal,
    access_params,
    allowed_cte,
    cited_access_cte,
)
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
    :threshold, :model, :prompt_version, :tokens_in, :tokens_out, CAST(:latency AS jsonb),
    CAST(:sources AS jsonb), :created_at)
""")
_INSERT_TRACE = text("""
INSERT INTO rag.message_traces (message_id, workspace_id, user_id, trace_version, trace)
VALUES (:msg, :wid, :uid, 1, CAST(:trace AS jsonb))
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
SELECT id, role, content, outcome, refusal_reason, context_sources, created_at FROM rag.messages
 WHERE conversation_id = :cid AND workspace_id = :wid AND user_id = :uid
 ORDER BY created_at, role DESC
""")

# Every document the answer was generated from: each source of the prompt (context_sources) and,
# as a fail-closed backstop, each citation. Citations alone miss answers the model wrote from a
# source without a valid [n] (TECH-V2-ai-service §7.5, owner decision 2026-11-09).
_HIDDEN = text(f"""
WITH {cited_access_cte()},
used AS (
    SELECT m.id AS message_id, CAST(s.value->>'documentId' AS uuid) AS document_id
      FROM rag.messages m
     CROSS JOIN LATERAL jsonb_array_elements(coalesce(m.context_sources, CAST('[]' AS jsonb))) s
     WHERE m.workspace_id = :wid AND m.user_id = :uid AND m.id = ANY (CAST(:ids AS uuid[]))
    UNION
    SELECT mc.message_id, mc.document_id
      FROM rag.message_citations mc
     WHERE mc.workspace_id = :wid AND mc.message_id = ANY (CAST(:ids AS uuid[]))
)
SELECT u.message_id,
       bool_or(ca.document_id IS NULL OR ca.deleted) AS deleted
  FROM used u
  LEFT JOIN cited_access ca ON ca.document_id = u.document_id
 GROUP BY u.message_id
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
_CITATION_CHUNKS = text(f"""
WITH {allowed_cte()}
SELECT c.id, c.ordinal, c.section_path, c.page_start, c.char_start, c.char_end, c.content
  FROM rag.chunks c
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
 WHERE c.workspace_id = :wid AND c.id = ANY (CAST(:ids AS uuid[]))
""")
_GET_ASSISTANT_MESSAGE = text("""
SELECT m.id, m.conversation_id, m.outcome, m.refusal_reason, m.standalone_query,
       m.rewrite_status, m.route, m.checks, m.lang, m.retrieval_mode, m.gate_score,
       m.threshold, m.model, m.prompt_version, m.tokens_in, m.tokens_out, m.latency_ms,
       m.context_sources
  FROM rag.messages m
  JOIN rag.conversations c ON c.id = m.conversation_id
 WHERE m.id = :mid AND m.conversation_id = :cid AND m.role = 'ASSISTANT'
   AND m.workspace_id = :wid AND m.user_id = :uid
   AND c.workspace_id = :wid AND c.user_id = :uid AND c.deleted_at IS NULL
""")
_GET_TRACE = text("""
SELECT trace FROM rag.message_traces
 WHERE message_id = :mid AND workspace_id = :wid AND user_id = :uid
""")
_GET_GUARD_EVENTS = text("""
SELECT layer, rule_id FROM rag.guard_events
 WHERE message_id = :mid AND workspace_id = :wid AND user_id = :uid
 ORDER BY created_at
""")
_COUNT_CITATIONS = text("""
SELECT count(*) FROM rag.message_citations
 WHERE message_id = :mid AND workspace_id = :wid
""")
_RETRIEVAL_CHUNKS = text(f"""
WITH {allowed_cte()}
SELECT rr.rank, rr.chunk_id, rr.dense_score, rr.bm25_score, rr.fusion_score,
       rr.rerank_score, rr.in_context,
       c.document_id, c.version_id, c.ordinal, c.chunk_type, c.section_path,
       c.page_start, c.token_count, c.content, a.title
  FROM rag.retrieval_results rr
  JOIN rag.chunks c ON c.id = rr.chunk_id AND c.workspace_id = :wid
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
 WHERE rr.workspace_id = :wid AND rr.message_id = :mid
 ORDER BY rr.rank
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
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: dict[str, int] = field(default_factory=dict)
    context_sources: list[dict] | None = None
    citations: Sequence[Citation] = ()
    guard_events: Sequence[GuardEvent] = ()
    retrieval: RetrievalResult | None = None
    trace: dict[str, Any] | None = None


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
             "threshold": None, "model": None, "prompt_version": None, "tokens_in": None,
             "tokens_out": None, "latency": None, "sources": None}
    await conn.execute(_INSERT_MESSAGE, {
        **common, **blank, "id": rec.user_message_id, "role": "USER", "content": rec.question,
        "lang": rec.lang, "created_at": rec.user_created})
    await conn.execute(_INSERT_MESSAGE, {
        **common, "id": rec.assistant_message_id, "role": "ASSISTANT", "content": rec.answer,
        "standalone": rec.standalone_query, "outcome": rec.outcome, "reason": rec.refusal_reason,
        "route": _json(rec.route), "rewrite_status": rec.rewrite_status,
        "checks": _json(rec.checks), "lang": rec.lang, "mode": rec.retrieval_mode,
        "gate": rec.gate_score, "threshold": rec.threshold, "model": rec.model,
        "prompt_version": rec.prompt_version, "tokens_in": rec.tokens_in,
        "tokens_out": rec.tokens_out, "latency": _json(rec.latency_ms),
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
    if rec.trace is not None:
        await conn.execute(_INSERT_TRACE, {
            "msg": msg, "wid": wid, "uid": uid, "trace": _json(rec.trace)})


async def hidden_answers(conn: AsyncConnection, principal: Principal,
                         message_ids: Sequence[UUID]) -> dict[UUID, str]:
    """``message_id -> reason`` for answers generated from a document the asker can no longer read.

    "Generated from" is every source in the prompt (``context_sources``) plus every citation, so
    an answer without a valid ``[n]`` is covered too. One unreadable document hides the whole
    answer (TECH §7.5). ``DOCUMENT_DELETED`` when such a document is gone, else ``ACCESS_REVOKED``.
    """
    if not message_ids:
        return {}
    rows = (await conn.execute(_HIDDEN, {
        **access_params(principal), "uid": principal.user_id,
        "ids": [str(i) for i in message_ids]})).all()
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


async def previous_sources(conn: AsyncConnection, principal: Principal,
                           conversation_id: UUID) -> list[tuple[str, int | None]]:
    """``(title, page)`` of the citations of the last answered turn, for ``about_source`` (V2-27).

    Same visibility as reading the conversation back: a hidden answer gives nothing, and a
    citation to a document the caller can no longer read is left out.
    """
    rows = (await conn.execute(_RECENT, {
        "cid": conversation_id, "wid": principal.workspace_id, "uid": principal.user_id,
        "limit": 12})).all()
    last = next((r.id for r in rows if r.role == "ASSISTANT" and r.outcome == "ANSWERED"), None)
    if last is None or last in await hidden_answers(conn, principal, [last]):
        return []
    cites = (await conn.execute(_CITATIONS, {
        **access_params(principal), "ids": [str(last)]})).all()
    out: list[tuple[str, int | None]] = []
    for c in cites:
        item = (c.title, c.page_start)
        if c.title and item not in out:
            out.append(item)
    return out


async def list_conversations(conn: AsyncConnection, principal: Principal, *, limit: int = 50,
                             offset: int = 0) -> list[Any]:
    return list((await conn.execute(_LIST, {
        "wid": principal.workspace_id, "uid": principal.user_id, "limit": limit,
        "offset": offset})).all())


async def conversation_detail(conn: AsyncConnection, principal: Principal,
                              conversation_id: UUID) -> dict[str, Any] | None:
    """The conversation with its messages and citations, or ``None`` if it is not the caller's.

    An answer generated from a document the caller can no longer read (``hidden_answers``) is
    replaced by ``{hidden: true, reason}``; the question
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
    hit_ids_by_source: dict[tuple[UUID, int], list[UUID]] = {}
    all_hit_ids: list[str] = []
    for m in msgs:
        if m.role != "ASSISTANT" or m.id in hidden or not isinstance(m.context_sources, list):
            continue
        for src in m.context_sources:
            if not isinstance(src, dict) or not isinstance(src.get("n"), int):
                continue
            raw_ids = src.get("hitChunkIds") or []
            parsed: list[UUID] = []
            for raw in raw_ids:
                try:
                    uid_val = UUID(str(raw))
                    parsed.append(uid_val)
                    all_hit_ids.append(str(uid_val))
                except ValueError:
                    continue
            if parsed:
                hit_ids_by_source[(m.id, src["n"])] = parsed

    chunks_by_id: dict[UUID, Any] = {}
    if all_hit_ids:
        unique_ids = list(dict.fromkeys(all_hit_ids))
        crows = (await conn.execute(_CITATION_CHUNKS, {
            **access_params(principal), "ids": unique_ids})).all()
        chunks_by_id = {r.id: r for r in crows}

    cites: dict[UUID, list[dict[str, Any]]] = {}
    if ids:
        rows = (await conn.execute(_CITATIONS, {
            **access_params(principal), "ids": [str(i) for i in ids]})).all()
        for r in rows:
            src_hit_ids = hit_ids_by_source.get((r.message_id, r.n), [])
            hit_rows = sorted(
                (chunks_by_id[cid] for cid in src_hit_ids if cid in chunks_by_id),
                key=lambda x: x.ordinal,
            )
            cite_chunks = [
                {
                    "subN": f"{r.n}.{idx}",
                    "chunkId": str(ch.id),
                    "sectionPath": list(ch.section_path or []),
                    "page": ch.page_start,
                    "charStart": ch.char_start,
                    "charEnd": ch.char_end,
                    "snippet": ch.content,
                }
                for idx, ch in enumerate(hit_rows, start=1)
            ]
            section_path = list(hit_rows[0].section_path or []) if hit_rows else []
            cites.setdefault(r.message_id, []).append({
                "n": r.n, "documentId": str(r.document_id), "versionId": str(r.version_id),
                "title": r.title, "page": r.page_start, "charStart": r.char_start,
                "charEnd": r.char_end, "snippet": r.snippet,
                "isCurrentVersion": bool(r.current), "sectionPath": section_path,
                "chunks": cite_chunks})
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


async def message_trace(conn: AsyncConnection, principal: Principal,
                        conversation_id: UUID, message_id: UUID) -> dict[str, Any] | None:
    """Pipeline trace for one assistant message owned by the caller, or ``None`` (404).

    Enforces current document read access (FR-19 / FR-25):
    - If any source document was deleted or revoked (``hidden_answers``), all chunk, source and
      prompt contents are stripped and ``hidden: true`` is returned.
    - Retrieved chunks are always hydrated live through ``allowed_cte()`` so revoked chunks are
      never returned even on ``NO_EVIDENCE`` turns.
    """
    wid, uid = principal.workspace_id, principal.user_id
    msg = (await conn.execute(_GET_ASSISTANT_MESSAGE, {
        "mid": message_id, "cid": conversation_id, "wid": wid, "uid": uid})).first()
    if msg is None:
        return None

    hidden = await hidden_answers(conn, principal, [message_id])
    trace_row = (await conn.execute(_GET_TRACE, {
        "mid": message_id, "wid": wid, "uid": uid})).first()

    if message_id in hidden:
        base = (
            dict(trace_row.trace)
            if trace_row is not None and isinstance(trace_row.trace, dict)
            else synthesize_legacy_trace(
                message_id=message_id, conversation_id=conversation_id, row=msg,
                guard_events=(), citations_count=0, chunks=[])
        )
        base.update({"messageId": str(message_id), "conversationId": str(conversation_id)})
        return strip_document_data(base, reason=hidden[message_id])

    chunk_rows = (await conn.execute(_RETRIEVAL_CHUNKS, {
        **access_params(principal), "mid": message_id})).all()
    chunks: list[dict[str, Any]] = []
    for r in chunk_rows:
        clean = " ".join(r.content.split())
        preview = clean[:180].rstrip() + "…" if len(clean) > 180 else clean
        chunks.append({
            "rank": r.rank,
            "chunkId": str(r.chunk_id),
            "documentId": str(r.document_id),
            "versionId": str(r.version_id),
            "title": r.title,
            "sectionPath": list(r.section_path or []),
            "page": r.page_start,
            "chunkType": r.chunk_type,
            "tokenCount": r.token_count,
            "denseScore": round(float(r.dense_score), 4) if r.dense_score is not None else None,
            "bm25Score": round(float(r.bm25_score), 4) if r.bm25_score is not None else None,
            "fusionScore": round(float(r.fusion_score), 4) if r.fusion_score is not None else None,
            "rerankScore": round(float(r.rerank_score), 4) if r.rerank_score is not None else None,
            "docCodeMatch": False,
            "inContext": bool(r.in_context),
            "preview": preview,
            "content": r.content,
        })

    if trace_row is not None and isinstance(trace_row.trace, dict):
        data = dict(trace_row.trace)
        data.update({
            "messageId": str(message_id),
            "conversationId": str(conversation_id),
            "reconstructed": False,
            "hidden": False,
            "hiddenReason": None,
            "chunks": chunks,
        })
        return data

    guards = (await conn.execute(_GET_GUARD_EVENTS, {
        "mid": message_id, "wid": wid, "uid": uid})).all()
    cite_count = int((await conn.execute(_COUNT_CITATIONS, {
        "mid": message_id, "wid": wid})).scalar_one() or 0)
    return synthesize_legacy_trace(
        message_id=message_id, conversation_id=conversation_id, row=msg,
        guard_events=guards, citations_count=cite_count, chunks=chunks)
