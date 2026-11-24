"""SQL of answer feedback and the knowledge-gap list (TECH-V2-ai-service §7.6).

Every statement filters ``workspace_id = :wid`` next to RLS. Feedback is written only by the
owner of the conversation, and only on an ``ASSISTANT`` message. The gap list never returns the
asker's identity; its questions are the PII-masked text (``qa/pii.py``).
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.feedback.gaps import (
    DOWNVOTE,
    EXCLUDED_OUTCOMES,
    EXCLUDED_REFUSAL_REASONS,
    GAP_REFUSAL_REASONS,
)
from sopilot_ai.retrieval.access_filter import Principal


def _in(values: tuple[str, ...]) -> str:
    """SQL literal list from trusted module constants (never from request input)."""
    return ", ".join(f"'{v}'" for v in values)


_ASSISTANT_OF_OWN_CONVERSATION = """
SELECT m.id FROM rag.messages m
  JOIN rag.conversations c ON c.id = m.conversation_id
 WHERE m.id = :mid AND m.workspace_id = :wid AND m.role = 'ASSISTANT'
   AND c.user_id = :uid AND c.deleted_at IS NULL
"""
_UPSERT_FEEDBACK = text("""
INSERT INTO rag.message_feedback (workspace_id, message_id, user_id, vote, comment)
VALUES (:wid, :mid, :uid, :vote, :comment)
ON CONFLICT (message_id, user_id) DO UPDATE
   SET vote = EXCLUDED.vote, comment = EXCLUDED.comment
""")

# One gap criterion, shared by the list and by "resolve" (a message that is not a gap cannot be
# resolved). "Answered without a citation" is checked on the stored decision log.
_GAP_WHERE = f"""
 WHERE m.workspace_id = :wid AND m.role = 'ASSISTANT'
   AND (m.outcome IS NULL OR m.outcome NOT IN ({_in(EXCLUDED_OUTCOMES)}))
   AND (m.refusal_reason IS NULL OR m.refusal_reason NOT IN ({_in(EXCLUDED_REFUSAL_REASONS)}))
   AND (m.refusal_reason IN ({_in(GAP_REFUSAL_REASONS)})
        OR (m.outcome = 'ANSWERED' AND m.checks->>'citationCount' = '0')
        OR EXISTS (SELECT 1 FROM rag.message_feedback d
                    WHERE d.message_id = m.id AND d.workspace_id = :wid AND d.vote = {DOWNVOTE}))
"""
_IS_GAP = text(f"SELECT m.id FROM rag.messages m {_GAP_WHERE} AND m.id = :mid")

_GAP_LIST = text(f"""
SELECT m.id, m.outcome, m.refusal_reason, m.created_at, q.content AS question,
       ks.resolved_at, ks.note AS resolution_note,
       (SELECT count(*) FROM rag.message_feedback d
         WHERE d.message_id = m.id AND d.workspace_id = :wid AND d.vote = {DOWNVOTE}) AS downvotes,
       (SELECT count(*) FROM rag.message_feedback d
         WHERE d.message_id = m.id AND d.workspace_id = :wid AND d.vote = 1) AS upvotes
  FROM rag.messages m
  LEFT JOIN LATERAL (
        SELECT u.content FROM rag.messages u
         WHERE u.conversation_id = m.conversation_id AND u.role = 'USER'
           AND u.workspace_id = :wid AND u.created_at < m.created_at
         ORDER BY u.created_at DESC LIMIT 1) q ON true
  LEFT JOIN rag.knowledge_gap_status ks
         ON ks.message_id = m.id AND ks.workspace_id = :wid
{_GAP_WHERE}
   AND ((:status = 'open' AND ks.message_id IS NULL)
        OR (:status = 'resolved' AND ks.message_id IS NOT NULL))
 ORDER BY m.created_at DESC, m.id
 LIMIT :limit OFFSET :offset
""")
_COMMENTS = text("""
SELECT message_id, vote, comment FROM rag.message_feedback
 WHERE workspace_id = :wid AND message_id = ANY(CAST(:ids AS uuid[]))
   AND comment IS NOT NULL
 ORDER BY created_at
""")
_RESOLVE = text("""
INSERT INTO rag.knowledge_gap_status (workspace_id, message_id, resolved_by, note)
VALUES (:wid, :mid, :uid, :note)
ON CONFLICT (message_id) DO NOTHING
""")


async def upsert_feedback(conn: AsyncConnection, principal: Principal, message_id: UUID,
                          vote: int, comment: str | None) -> bool:
    """``False`` when the message is not an answer in the caller's own conversation."""
    own = (await conn.execute(text(_ASSISTANT_OF_OWN_CONVERSATION), {
        "mid": message_id, "wid": principal.workspace_id, "uid": principal.user_id})).first()
    if own is None:
        return False
    await conn.execute(_UPSERT_FEEDBACK, {
        "wid": principal.workspace_id, "mid": message_id, "uid": principal.user_id,
        "vote": vote, "comment": comment})
    return True


async def gap_list(conn: AsyncConnection, principal: Principal, *,
                   status: Literal["open", "resolved"], limit: int, offset: int
                   ) -> tuple[list[Any], dict[UUID, list[Any]]]:
    rows = (await conn.execute(_GAP_LIST, {
        "wid": principal.workspace_id, "status": status, "limit": limit, "offset": offset,
    })).all()
    comments: dict[UUID, list[Any]] = {}
    if rows:
        for c in (await conn.execute(_COMMENTS, {
                "wid": principal.workspace_id, "ids": [str(r.id) for r in rows]})).all():
            comments.setdefault(c.message_id, []).append(c)
    return list(rows), comments


async def resolve_gap(conn: AsyncConnection, principal: Principal, message_id: UUID,
                      note: str | None) -> bool:
    """``False`` when the message is not (or no longer) a knowledge gap in this workspace."""
    found = (await conn.execute(_IS_GAP, {"wid": principal.workspace_id,
                                          "mid": message_id})).first()
    if found is None:
        return False
    await conn.execute(_RESOLVE, {"wid": principal.workspace_id, "mid": message_id,
                                  "uid": principal.user_id, "note": note})
    return True
