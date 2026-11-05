"""``rag.retrieval_results``: every candidate with its four scores (TECH-V2-ai-service §6.4)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.retrieval.retriever import RetrievalResult

_INSERT = text("""
INSERT INTO rag.retrieval_results (workspace_id, message_id, chunk_id, rank, dense_score,
                                   bm25_score, fusion_score, rerank_score, in_context)
VALUES (:wid, :msg, :chunk, :rank, :dense, :bm25, :fusion, :rerank, :in_context)
""")


async def save(conn: AsyncConnection, workspace_id: UUID, message_id: UUID,
               result: RetrievalResult) -> int:
    """Write all ``rerank_pool`` candidates; ``in_context`` marks the hit chunks."""
    hits = {c.chunk_id for c in result.hits}
    rows = [{
        "wid": workspace_id, "msg": message_id, "chunk": c.chunk_id, "rank": c.rank,
        "dense": c.dense_score, "bm25": c.bm25_score, "fusion": c.fusion_score,
        "rerank": c.rerank_score, "in_context": c.chunk_id in hits,
    } for c in result.candidates]
    if rows:
        await conn.execute(_INSERT, rows)
    return len(rows)
