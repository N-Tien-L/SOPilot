"""``rag.embedding_cache`` keyed by ``(model, revision, sha256(index_text))`` (§5.5)."""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.db.engine import parse_vector, vector_literal


async def get_many(conn: AsyncConnection, model: str, revision: str,
                   hashes: Sequence[bytes]) -> dict[bytes, np.ndarray]:
    if not hashes:
        return {}
    rows = await conn.execute(text(
        "SELECT content_sha256, embedding::text FROM rag.embedding_cache "
        "WHERE model = :m AND revision = :r AND content_sha256 = ANY(:h)"),
        {"m": model, "r": revision, "h": list(hashes)})
    return {bytes(h): parse_vector(v) for h, v in rows}


async def put_many(conn: AsyncConnection, model: str, revision: str,
                   items: Iterable[tuple[bytes, np.ndarray]]) -> None:
    params = [{"m": model, "r": revision, "h": h, "v": vector_literal(v)} for h, v in items]
    if params:
        await conn.execute(text(
            "INSERT INTO rag.embedding_cache (model, revision, content_sha256, embedding) "
            "VALUES (:m, :r, :h, CAST(:v AS vector)) ON CONFLICT DO NOTHING"), params)
