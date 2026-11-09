"""SQL behind context assembly (TECH-V2-ai-service §6.4a); the pure part is ``context.py``.

Every query starts from ``allowed_cte()`` and repeats ``workspace_id = :wid``, so the chunks
that widen a hit into its section are filtered exactly like the hit itself: there is no second
access filter and no path to a chunk the asker may not read.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.retrieval.access_filter import Principal, access_params, allowed_cte
from sopilot_ai.retrieval.context import ChunkInfo, GroupKey

_COLUMNS = """c.id, c.document_id, c.version_id, c.ordinal, c.chunk_type, c.section_path,
       c.page_start, c.char_start, c.char_end, c.content, c.token_count"""

_BY_ID = text(f"""
WITH {allowed_cte()}
SELECT {_COLUMNS}
  FROM rag.chunks c
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
 WHERE c.workspace_id = :wid AND c.id = ANY (CAST(:ids AS uuid[]))
""")

_SECTIONS = text(f"""
WITH {allowed_cte()}
SELECT {_COLUMNS}
  FROM rag.chunks c
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
  JOIN jsonb_to_recordset(CAST(:keys AS jsonb)) AS k(v uuid, p jsonb)
    ON c.version_id = k.v AND to_jsonb(c.section_path) = k.p
 WHERE c.workspace_id = :wid
 ORDER BY c.version_id, c.ordinal
""")

_META = text(f"""
WITH {allowed_cte()}
SELECT e.version_id, a.title,
       e.extracted_meta->>'docCode' AS code,
       e.extracted_meta->>'revisionLabel' AS rev,
       e.extracted_meta->>'effectiveDate' AS effective
  FROM rag.extracted_documents e
  JOIN allowed a ON a.document_id = e.document_id AND a.active_version_id = e.version_id
 WHERE e.workspace_id = :wid AND e.version_id = ANY (CAST(:versions AS uuid[]))
""")


@dataclass(frozen=True)
class VersionInfo:
    """What the prompt shows about a source's document (TECH §7.1 step 6, D3)."""

    title: str | None
    code: str | None = None
    rev: str | None = None
    effective: str | None = None


def _chunk(row: Any) -> ChunkInfo:
    return ChunkInfo(row.id, row.document_id, row.version_id, row.ordinal, row.chunk_type,
                     tuple(row.section_path), row.page_start, row.char_start, row.char_end,
                     row.content, row.token_count)


async def load_chunks(conn: AsyncConnection, principal: Principal,
                      ids: Sequence[UUID]) -> list[ChunkInfo]:
    """The chunks of ``ids`` the asker may read, in the order of ``ids``."""
    if not ids:
        return []
    rows = (await conn.execute(_BY_ID, {
        **access_params(principal), "ids": [str(i) for i in ids]})).all()
    by_id = {r.id: _chunk(r) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


async def load_sections(conn: AsyncConnection, principal: Principal,
                        keys: Sequence[GroupKey]) -> Mapping[GroupKey, list[ChunkInfo]]:
    """All chunks of each ``(version_id, section_path)`` the asker may read, by ordinal."""
    if not keys:
        return {}
    payload = json.dumps([{"v": str(v), "p": list(path)} for v, path in keys])
    rows = (await conn.execute(_SECTIONS, {**access_params(principal), "keys": payload})).all()
    groups: dict[GroupKey, list[ChunkInfo]] = {}
    for r in rows:
        chunk = _chunk(r)
        groups.setdefault((chunk.version_id, chunk.section_path), []).append(chunk)
    return groups


async def load_version_info(conn: AsyncConnection, principal: Principal,
                            versions: Sequence[UUID]) -> dict[UUID, VersionInfo]:
    """Title and ``code``/``rev``/``effective`` of the active versions the asker may read."""
    if not versions:
        return {}
    rows = (await conn.execute(_META, {
        **access_params(principal), "versions": [str(v) for v in versions]})).all()
    return {r.version_id: VersionInfo(r.title, r.code, r.rev, r.effective) for r in rows}
