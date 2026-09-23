import httpx
from typing import List, Optional
import structlog
import math

from ...config.settings import settings
from ...db.repositories.chunk_repo import chunk_repository
from ...models.retrieval import RetrievalChunk, RetrievalFilters

logger = structlog.get_logger()


class EmbeddingService:
    def __init__(self):
        self.embedding_url = settings.embedding_url

    async def embed_query(self, query: str) -> List[float]:
        headers = {"Content-Type": "application/json"}
        if settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {settings.embedding_api_key}"

        base_url = self.embedding_url.rstrip("/")
        endpoint = f"{base_url}/v1/embeddings" if not base_url.endswith("/v1/embeddings") else base_url

        payload = {
            "input": [query],
            "model": settings.embedding_model
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload
            )
            if response.status_code != 200:
                logger.error("embedding_failed", status=response.status_code, response=response.text)
                raise Exception(f"Embedding failed: {response.status_code}")

            data = response.json()
            return data["data"][0]["embedding"]


embedding_service = EmbeddingService()


class HybridSearchService:
    def __init__(self):
        self.embedding_service = embedding_service
        self.chunk_repo = chunk_repository

    async def search(
        self,
        query: str,
        user_id: str,
        user_role: str,
        user_department_id: Optional[str] = None,
        filters: Optional[RetrievalFilters] = None,
        limit: int = 10
    ) -> List[RetrievalChunk]:
        logger.info("hybrid_search_start", query=query, limit=limit)

        query_embedding = await self.embedding_service.embed_query(query)

        vector_results = await self.chunk_repo.vector_search(
            query_embedding=query_embedding,
            user_id=user_id,
            user_role=user_role,
            user_department_id=user_department_id,
            filters=filters,
            limit=limit * 2
        )

        logger.info("hybrid_search_vector_results",
            query=query,
            count=len(vector_results),
            top_docs=[{"doc": c.document_name, "score": c.similarity_score} for c in vector_results[:5]]
        )

        bm25_results = await self.chunk_repo.bm25_search(
            query=query,
            user_id=user_id,
            user_role=user_role,
            user_department_id=user_department_id,
            filters=filters,
            limit=limit * 2
        )

        logger.info("hybrid_search_bm25_results",
            query=query,
            count=len(bm25_results),
            top_docs=[{"doc": c.document_name, "score": c.similarity_score} for c in bm25_results[:5]]
        )

        fused = self._reciprocal_rank_fusion(vector_results, bm25_results, k=60, alpha=0.7, beta=0.3)

        filtered = [c for c in fused if c.similarity_score >= settings.similarity_threshold]

        logger.info("hybrid_search_final",
            query=query,
            before_filter=len(fused),
            after_filter=len(filtered),
            threshold=settings.similarity_threshold,
            top_docs=[{"doc": c.document_name, "score": c.similarity_score, "excerpt": c.content[:100]} for c in filtered[:5]]
        )

        return filtered[:limit]

    def _reciprocal_rank_fusion(
        self,
        results_a: List[RetrievalChunk],
        results_b: List[RetrievalChunk],
        k: int = 60,
        alpha: float = 0.7,
        beta: float = 0.3
    ) -> List[RetrievalChunk]:
        scores = {}

        for rank, chunk in enumerate(results_a):
            key = str(chunk.id)
            scores[key] = scores.get(key, 0) + alpha * (1.0 / (k + rank + 1))
            chunk._source = "vector"

        for rank, chunk in enumerate(results_b):
            key = str(chunk.id)
            scores[key] = scores.get(key, 0) + beta * (1.0 / (k + rank + 1))
            if key not in {str(c.id) for c in results_a}:
                chunk._source = "bm25"

        all_chunks = {str(c.id): c for c in results_a}
        for c in results_b:
            if str(c.id) not in all_chunks:
                all_chunks[str(c.id)] = c

        sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [all_chunks[k] for k in sorted_keys]


hybrid_search_service = HybridSearchService()