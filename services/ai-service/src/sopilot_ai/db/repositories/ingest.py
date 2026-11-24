"""Activation of a processed version in one transaction (TECH-V2-ai-service §5.6)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sopilot_ai.db.engine import vector_literal


@dataclass(frozen=True)
class ChunkRow:
    id: UUID
    ordinal: int
    chunk_type: str
    section_path: list[str]
    page_start: int | None
    page_end: int | None
    char_start: int
    char_end: int
    content: str
    index_text: str
    lang: str | None
    token_count: int
    content_sha256: bytes
    embedding: np.ndarray
    lexical_len: int
    terms: dict[str, int]


@dataclass(frozen=True)
class ExtractedRow:
    structure: dict[str, Any]
    markdown: str
    page_index: list[dict[str, int]] | None
    warnings: list[dict[str, Any]]
    normalizer_version: str
    page_count: int | None
    language: str | None
    doc_family: str
    boilerplate: list[dict[str, Any]]
    extracted_meta: dict[str, Any]
    extractor: str


@dataclass(frozen=True)
class EmbeddingInfo:
    provider: str
    model: str
    revision: str
    dim: int


_INSERT_CHUNK = text("""
INSERT INTO rag.chunks (id, workspace_id, document_id, version_id, ordinal, chunk_type,
                        section_path, page_start, page_end, char_start, char_end, content,
                        index_text, lang, token_count, content_sha256, embedding,
                        embedding_provider, embedding_model, embedding_dim, embedding_revision,
                        lexical_len)
VALUES (:id, :wid, :doc, :ver, :ordinal, :type, CAST(:path AS text[]), :ps, :pe, :cs, :ce,
        :content, :index_text, :lang, :tokens, :sha, CAST(:emb AS vector), :provider, :model,
        :dim, :rev, :llen)
""")

_INSERT_TERM = text("INSERT INTO rag.chunk_terms (workspace_id, chunk_id, term, tf) "
                    "VALUES (:wid, :cid, :term, :tf)")

_INSERT_EXTRACTED = text("""
INSERT INTO rag.extracted_documents (workspace_id, version_id, document_id, structure, markdown,
                                     page_index, warnings, normalizer_version, page_count, language,
                                     doc_family, boilerplate, extracted_meta, extractor)
VALUES (:wid, :ver, :doc, CAST(:structure AS jsonb), :markdown, CAST(:page_index AS jsonb),
        CAST(:warnings AS jsonb), :nv, :pages, :lang, :family, CAST(:boilerplate AS jsonb),
        CAST(:meta AS jsonb), :extractor)
""")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


async def activate_version(conn: AsyncConnection, *, workspace_id: UUID, document_id: UUID,
                           version_id: UUID, title: str, extracted: ExtractedRow,
                           chunks: list[ChunkRow], embedding: EmbeddingInfo) -> bool:
    """Steps 1–3 of §5.6. Returns False (caller rolls back) when the document is gone.

    Rows of the same version are replaced first, so ``admin reindex`` of an active version and a
    re-run after a crash both land on a clean slate.
    """
    base = {"wid": workspace_id, "doc": document_id, "ver": version_id}
    await conn.execute(text(
        "DELETE FROM rag.chunks WHERE workspace_id = :wid AND version_id = :ver"), base)
    await conn.execute(text(
        "DELETE FROM rag.extracted_documents WHERE workspace_id = :wid AND version_id = :ver"),
        base)
    await conn.execute(_INSERT_EXTRACTED, {
        **base,
        "structure": _json(extracted.structure),
        "markdown": extracted.markdown,
        "page_index": _json(extracted.page_index) if extracted.page_index is not None else None,
        "warnings": _json(extracted.warnings),
        "nv": extracted.normalizer_version,
        "pages": extracted.page_count,
        "lang": extracted.language,
        "family": extracted.doc_family,
        "boilerplate": _json(extracted.boilerplate),
        "meta": _json(extracted.extracted_meta),
        "extractor": extracted.extractor,
    })
    await conn.execute(_INSERT_CHUNK, [{
        **base, "id": c.id, "ordinal": c.ordinal, "type": c.chunk_type, "path": c.section_path,
        "ps": c.page_start, "pe": c.page_end, "cs": c.char_start, "ce": c.char_end,
        "content": c.content, "index_text": c.index_text, "lang": c.lang, "tokens": c.token_count,
        "sha": c.content_sha256, "emb": vector_literal(c.embedding), "provider": embedding.provider,
        "model": embedding.model, "dim": embedding.dim, "rev": embedding.revision,
        "llen": c.lexical_len,
    } for c in chunks])
    terms = [{"wid": workspace_id, "cid": c.id, "term": t, "tf": tf}
             for c in chunks for t, tf in c.terms.items()]
    if terms:
        await conn.execute(_INSERT_TERM, terms)
    updated = (await conn.execute(text("""
        UPDATE rag.document_access SET active_version_id = :ver, title = :title
         WHERE workspace_id = :wid AND document_id = :doc AND deleted_at IS NULL
        RETURNING document_id"""), {**base, "title": title})).first()
    if updated is None:
        return False
    await conn.execute(text(
        "DELETE FROM rag.chunks WHERE workspace_id = :wid AND document_id = :doc "
        "AND version_id <> :ver"), base)
    return True
