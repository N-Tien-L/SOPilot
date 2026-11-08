"""SQL of the retrieval branches (TECH-V2-ai-service §6.2, §6.3, §6.4).

Every query starts from ``allowed_cte()``, so the access filter applies in ``WHERE``/``JOIN``
before ``LIMIT`` (FR-25), and repeats ``workspace_id = :wid`` next to RLS. The f-strings below
only splice that constant CTE at import time; every request value is a bound parameter.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.db.engine import vector_literal
from sopilot_ai.retrieval.access_filter import Principal, access_params, allowed_cte
from sopilot_ai.retrieval.lexical import K1, B


@dataclass(frozen=True)
class Hit:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    lang: str | None
    score: float


_DENSE = text(f"""
WITH {allowed_cte()}
SELECT c.id, c.document_id, c.version_id, c.lang,
       1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
  FROM rag.chunks c
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
 WHERE c.workspace_id = :wid
   AND c.embedding_model = :model AND c.embedding_revision = :rev
 ORDER BY c.embedding <=> CAST(:qvec AS vector)
 LIMIT :pool
""")

_BM25 = text(f"""
WITH {allowed_cte()},
scope AS (
    SELECT c.id, c.document_id, c.version_id, c.lang, c.lexical_len
      FROM rag.chunks c
      JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
     WHERE c.workspace_id = :wid
),
stats AS (SELECT count(*)::float8 AS n, avg(lexical_len)::float8 AS avgdl FROM scope),
q AS (SELECT DISTINCT unnest(CAST(:terms AS text[])) AS term),
df AS (
    SELECT t.term, count(*)::float8 AS df
      FROM rag.chunk_terms t
      JOIN scope s ON s.id = t.chunk_id
      JOIN q ON q.term = t.term
     WHERE t.workspace_id = :wid
     GROUP BY t.term
)
SELECT s.id, s.document_id, s.version_id, s.lang,
       sum( ln(1 + (st.n - df.df + 0.5) / (df.df + 0.5))
            * t.tf * (:k1 + 1)
            / (t.tf + :k1 * (1 - :b + :b * s.lexical_len / nullif(st.avgdl, 0))) ) AS score
  FROM rag.chunk_terms t
  JOIN scope s ON s.id = t.chunk_id
  JOIN df ON df.term = t.term
 CROSS JOIN stats st
 WHERE t.workspace_id = :wid
 GROUP BY s.id, s.document_id, s.version_id, s.lang
 ORDER BY score DESC, s.id
 LIMIT :pool
""")

_COSINE_BY_ID = text(f"""
WITH {allowed_cte()}
SELECT c.id, 1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
  FROM rag.chunks c
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
 WHERE c.workspace_id = :wid
   AND c.id = ANY (CAST(:ids AS uuid[]))
   AND c.embedding_model = :model AND c.embedding_revision = :rev
""")

_DOC_CODES = text(f"""
WITH {allowed_cte()}
SELECT e.version_id, e.extracted_meta->>'docCode' AS doc_code
  FROM rag.extracted_documents e
  JOIN allowed a ON a.document_id = e.document_id AND a.active_version_id = e.version_id
 WHERE e.workspace_id = :wid
   AND e.version_id = ANY (CAST(:versions AS uuid[]))
   AND e.extracted_meta->>'docCode' IS NOT NULL
""")

_TEXTS = text(f"""
WITH {allowed_cte()}
SELECT c.id, c.index_text
  FROM rag.chunks c
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
 WHERE c.workspace_id = :wid
   AND c.id = ANY (CAST(:ids AS uuid[]))
""")


def _hits(rows: Sequence[Any]) -> list[Hit]:
    return [Hit(r.id, r.document_id, r.version_id, r.lang, float(r.score)) for r in rows]


async def dense(conn: AsyncConnection, principal: Principal, qvec: np.ndarray, *, model: str,
                revision: str, pool: int) -> list[Hit]:
    """Top ``pool`` chunks by cosine, embedded by the active ``(model, revision)`` only."""
    # pgvector ≥ 0.8: keep scanning the HNSW graph when the filter drops candidates (§6.2).
    await conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    await conn.execute(text("SET LOCAL hnsw.ef_search = 100"))
    rows = (await conn.execute(_DENSE, {
        **access_params(principal), "qvec": vector_literal(qvec), "model": model, "rev": revision,
        "pool": pool,
    })).all()
    # relaxed_order may return neighbours slightly out of order; rank by the exact score.
    return sorted(_hits(rows), key=lambda h: (-h.score, str(h.chunk_id)))


async def bm25(conn: AsyncConnection, principal: Principal, terms: Sequence[str], *,
               pool: int) -> list[Hit]:
    """Top ``pool`` chunks by BM25 with N, df and avgdl over the chunks the asker may read."""
    unique = list(dict.fromkeys(terms))
    if not unique:
        return []
    rows = (await conn.execute(_BM25, {
        **access_params(principal), "terms": unique, "k1": K1, "b": B, "pool": pool,
    })).all()
    return _hits(rows)


async def cosine_by_id(conn: AsyncConnection, principal: Principal, qvec: np.ndarray,
                       ids: Sequence[UUID], *, model: str, revision: str) -> dict[UUID, float]:
    """Direct cosine for candidates the dense branch did not return (§6.4, D2)."""
    if not ids:
        return {}
    rows = (await conn.execute(_COSINE_BY_ID, {
        **access_params(principal), "qvec": vector_literal(qvec),
        "ids": [str(i) for i in ids], "model": model, "rev": revision,
    })).all()
    return {r.id: float(r.score) for r in rows}


async def doc_codes(conn: AsyncConnection, principal: Principal,
                    versions: Sequence[UUID]) -> dict[UUID, str]:
    """``extracted_meta.docCode`` of the given active versions the asker may read."""
    if not versions:
        return {}
    rows = (await conn.execute(_DOC_CODES, {
        **access_params(principal), "versions": [str(v) for v in versions],
    })).all()
    return {r.version_id: r.doc_code for r in rows}


async def index_texts(conn: AsyncConnection, principal: Principal,
                      ids: Sequence[UUID]) -> dict[UUID, str]:
    """``index_text`` (what was embedded) of candidates, for the reranker."""
    if not ids:
        return {}
    rows = (await conn.execute(_TEXTS, {
        **access_params(principal), "ids": [str(i) for i in ids],
    })).all()
    return {r.id: r.index_text for r in rows}
