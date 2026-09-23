from uuid import UUID
from typing import List, Optional
import asyncpg
import json
import structlog

from ...db.session import get_connection, release_connection
from ...models.retrieval import RetrievalChunk, RetrievalFilters

logger = structlog.get_logger()


class ChunkRepository:
    async def vector_search(
        self,
        query_embedding: List[float],
        user_id: UUID,
        user_role: str,
        user_department_id: Optional[UUID],
        filters: Optional[RetrievalFilters] = None,
        limit: int = 10
    ) -> List[RetrievalChunk]:
        conn = await get_connection()
        try:
            user_roles = [user_role]
            user_departments = [str(user_department_id)] if user_department_id else []
            user_ids = [str(user_id)]

            filters_parts = []
            param_offset = 5
            if filters and filters.document_ids:
                filters_parts.append(f"AND c.document_id = ANY(${param_offset})")
                param_offset += 1
            if filters and filters.category_ids:
                filters_parts.append(f"AND dm.category_id = ANY(${param_offset})")
                param_offset += 1

            doc_filter = " ".join(filters_parts)

            params = [str(query_embedding), user_roles, user_departments, user_ids]
            if filters and filters.document_ids:
                params.append([str(d) for d in filters.document_ids])
            if filters and filters.category_ids:
                params.append([str(c) for c in filters.category_ids])
            params.append(limit)

            dept_boost_expr = ""
            if user_department_id:
                dept_boost_expr = f" - CASE WHEN c.department_id = '{user_department_id}' THEN 0.02 ELSE 0 END"

            query = f"""
                SELECT c.id, c.document_id, dm.title as document_name, c.content,
                       c.section_title, c.start_char_index, c.end_char_index,
                       ((c.embedding_vector <=> $1::vector){dept_boost_expr}) as distance,
                       c.metadata
                FROM knowledge.chunks c
                LEFT JOIN metadata.document_metadata dm ON dm.document_id = c.document_id AND dm.deleted_at IS NULL
                WHERE c.is_latest = true
                  AND c.deleted_at IS NULL
                  AND c.embedding_vector IS NOT NULL
                  AND dm.status = 'PUBLISHED'
                  AND (dm.expiry_date IS NULL OR dm.expiry_date > CURRENT_DATE)
                  AND (c.access_level = 'PUBLIC'
                       OR c.allowed_roles && $2::core.user_role[]
                       OR c.allowed_departments && $3::uuid[]
                       OR c.allowed_users && $4::uuid[])
                  {doc_filter}
                ORDER BY distance ASC
                LIMIT ${len(params)}
            """

            rows = await conn.fetch(query, *params)

            chunks = []
            for row in rows:
                distance = row['distance']
                similarity = 1.0 - distance if distance is not None else 0.0
                raw_metadata = row.get('metadata')
                chunks.append(RetrievalChunk(
                    id=row['id'],
                    document_id=row['document_id'],
                    document_name=row.get('document_name'),
                    content=row['content'],
                    section_title=row.get('section_title'),
                    similarity_score=similarity,
                    start_char_index=row.get('start_char_index'),
                    end_char_index=row.get('end_char_index'),
                    metadata=json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
                ))

            return chunks
        finally:
            await release_connection(conn)

    async def bm25_search(
        self,
        query: str,
        user_id: UUID,
        user_role: str,
        user_department_id: Optional[UUID],
        filters: Optional[RetrievalFilters] = None,
        limit: int = 10
    ) -> List[RetrievalChunk]:
        conn = await get_connection()
        try:
            user_roles = [user_role]
            user_departments = [str(user_department_id)] if user_department_id else []
            user_ids = [str(user_id)]

            filters_parts = []
            param_offset = 6
            if filters and filters.document_ids:
                filters_parts.append(f"AND c.document_id = ANY(${param_offset})")
                param_offset += 1
            if filters and filters.category_ids:
                filters_parts.append(f"AND dm.category_id = ANY(${param_offset})")
                param_offset += 1

            doc_filter = " ".join(filters_parts)

            params = [query, user_roles, user_departments, user_ids]
            if filters and filters.document_ids:
                params.append([str(d) for d in filters.document_ids])
            if filters and filters.category_ids:
                params.append([str(c) for c in filters.category_ids])
            params.append(limit)

            dept_boost_expr = ""
            if user_department_id:
                dept_boost_expr = f" + CASE WHEN c.department_id = '{user_department_id}' THEN 0.05 ELSE 0 END"

            sql_query = f"""
                SELECT c.id, c.document_id, dm.title as document_name, c.content,
                       c.section_title, c.start_char_index, c.end_char_index,
                       (ts_rank(
                           setweight(coalesce(c.content_tsv, ''::tsvector), 'D') ||
                           setweight(coalesce(to_tsvector('simple', dm.title), ''::tsvector), 'A') ||
                           setweight(coalesce(to_tsvector('simple', c.section_title), ''::tsvector), 'B'),
                           plainto_tsquery('simple', $1)
                       ){dept_boost_expr}) as rank,
                       c.metadata
                FROM knowledge.chunks c
                LEFT JOIN metadata.document_metadata dm ON dm.document_id = c.document_id AND dm.deleted_at IS NULL
                WHERE (
                    c.content_tsv @@ plainto_tsquery('simple', $1)
                    OR to_tsvector('simple', dm.title) @@ plainto_tsquery('simple', $1)
                    OR to_tsvector('simple', c.section_title) @@ plainto_tsquery('simple', $1)
                )
                  AND c.is_latest = true
                  AND c.deleted_at IS NULL
                  AND dm.status = 'PUBLISHED'
                  AND (dm.expiry_date IS NULL OR dm.expiry_date > CURRENT_DATE)
                  AND (c.access_level = 'PUBLIC'
                       OR c.allowed_roles && $2::core.user_role[]
                       OR c.allowed_departments && $3::uuid[]
                       OR c.allowed_users && $4::uuid[])
                  {doc_filter}
                ORDER BY rank DESC
                LIMIT ${len(params)}
            """

            rows = await conn.fetch(sql_query, *params)

            chunks = []
            max_rank = max((row.get('rank', 0) for row in rows), default=1)
            for row in rows:
                rank_score = row.get('rank', 0)
                if max_rank > 0:
                    normalized = rank_score / max_rank
                else:
                    normalized = 0.0
                similarity = float(min(normalized, 1.0))
                raw_metadata = row.get('metadata')
                chunks.append(RetrievalChunk(
                    id=row['id'],
                    document_id=row['document_id'],
                    document_name=row.get('document_name'),
                    content=row['content'],
                    section_title=row.get('section_title'),
                    similarity_score=similarity,
                    start_char_index=row.get('start_char_index'),
                    end_char_index=row.get('end_char_index'),
                    metadata=json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
                ))

            return chunks
        finally:
            await release_connection(conn)


chunk_repository = ChunkRepository()