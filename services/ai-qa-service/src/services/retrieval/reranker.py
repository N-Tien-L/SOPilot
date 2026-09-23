import httpx
from typing import List
import structlog

from ...config.settings import settings
from ...models.retrieval import RetrievalChunk

logger = structlog.get_logger()


class RerankerService:
    def __init__(self):
        self.reranker_url = settings.reranker_url
        self.enabled = settings.use_reranker and self.reranker_url

    async def rerank(
        self,
        query: str,
        chunks: List[RetrievalChunk],
        limit: int = 5
    ) -> List[RetrievalChunk]:
        if not self.enabled:
            return chunks[:limit]

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.reranker_url}/rerank",
                    json={
                        "query": query,
                        "texts": [chunk.content for chunk in chunks],
                        "truncate": True
                    }
                )

                if response.status_code != 200:
                    logger.warning("rerank_failed", status=response.status_code)
                    return chunks[:limit]

                results = response.json()

                ranked = sorted(results, key=lambda x: x["score"], reverse=True)
                reranked_chunks = []
                seen = set()

                for r in ranked:
                    idx = r["index"]
                    if idx not in seen:
                        seen.add(idx)
                        chunk = chunks[idx]
                        chunk.similarity_score = r["score"]
                        reranked_chunks.append(chunk)

                return reranked_chunks[:limit]

            except httpx.TimeoutException:
                logger.warning("rerank_timeout", reranker_url=self.reranker_url)
                return chunks[:limit]
            except Exception as e:
                logger.warning("rerank_error", error=str(e), reranker_url=self.reranker_url)
                return chunks[:limit]


reranker_service = RerankerService()