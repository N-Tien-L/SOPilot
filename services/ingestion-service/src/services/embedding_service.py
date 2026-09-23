"""Embedding service – generates vectors via HuggingFace TEI with Layer-3 cache.

Architecture
────────────
1. Caller passes a list of texts (chunk contents).
2. Each text is hashed (SHA-256).
3. Hashes are looked up in ``knowledge.embedding_cache``.
   • Cache HIT  → reuse the stored vector (zero API cost).
   • Cache MISS → collect the text into a batch for TEI.
4. Only the *misses* are sent to BGE-M3 via ``/v1/embeddings``.
5. Newly generated vectors are persisted back into the cache.
6. A merged, order-preserving result list is returned to the caller.

This approach guarantees that when a 100-page document is revised with
only 2 paragraphs changed, we embed exactly those 2 paragraphs instead
of the entire document again.
"""

import hashlib
import structlog
import httpx

from src.config.settings import settings

logger = structlog.get_logger()

EMBEDDING_MODEL_NAME = "BGE_M3"
EMBEDDING_DIMENSION = 1024


class EmbeddingService:
    """Service for generating embeddings via HuggingFace Text Embeddings Inference (TEI).

    TEI exposes an OpenAI-compatible REST API at /v1/embeddings.
    Request format:  {"input": ["text1", "text2"]}
    Response format: {"data": [{"embedding": [0.1, ...], "index": 0}, ...]}
    """

    def __init__(self):
        self.embedding_url = settings.embedding_url
        self.reranker_url = settings.reranker_url

    # ------------------------------------------------------------------
    # Core: embed without cache (direct TEI call)
    # ------------------------------------------------------------------
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts via TEI /v1/embeddings endpoint.

        Returns list of embedding vectors in the same order as *texts*.
        """
        if not texts:
            return []

        # Truncate texts to avoid "413 Payload Too Large" error
        # Let's import tiktoken and truncate each text to maximum 512 tokens
        import tiktoken
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            truncated_texts = []
            for text in texts:
                tokens = enc.encode(text)
                if len(tokens) > 512:
                    truncated_texts.append(enc.decode(tokens[:512]))
                else:
                    truncated_texts.append(text)
        except Exception as e:
            logger.warning("failed_to_truncate_tokens_falling_back_to_char_slice", error=str(e))
            truncated_texts = [text[:2000] for text in texts]

        headers = {"Content-Type": "application/json"}
        if settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {settings.embedding_api_key}"

        base_url = self.embedding_url.rstrip("/")
        endpoint = f"{base_url}/v1/embeddings" if not base_url.endswith("/v1/embeddings") else base_url

        payload = {
            "input": truncated_texts,
            "model": settings.embedding_model,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            # Standard OpenAI / Jina format: {"data": [{"embedding": [...], "index": 0}, ...]}
            items = sorted(data["data"], key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in items]

    # ------------------------------------------------------------------
    # Layer 3: cache-aware embedding
    # ------------------------------------------------------------------
    async def embed_batch_cached(
        self,
        texts: list[str],
        session,
    ) -> list[list[float]]:
        """Generate embeddings with Layer-3 chunk-level caching.

        1. Hash every text.
        2. Batch-lookup hashes in ``knowledge.embedding_cache``.
        3. Send only cache-misses to TEI.
        4. Persist new vectors back into the cache.
        5. Return a merged list preserving the original order of *texts*.

        Args:
            texts: ordered list of chunk contents.
            session: an active ``AsyncSession`` (caller owns the transaction).

        Returns:
            Ordered list of embedding vectors, one per input text.
        """
        if not texts:
            return []

        from src.db.repositories.embedding_cache_repo import EmbeddingCacheRepository
        cache_repo = EmbeddingCacheRepository(session)

        # Step 1 — compute hashes
        hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]

        # Step 2 — batch cache lookup
        cache_hits = await cache_repo.lookup_batch(hashes, EMBEDDING_MODEL_NAME)
        hit_count = len(cache_hits)

        # Step 3 — identify misses
        miss_indices: list[int] = []
        miss_texts: list[str] = []
        for idx, h in enumerate(hashes):
            if h not in cache_hits:
                miss_indices.append(idx)
                miss_texts.append(texts[idx])

        logger.info(
            "embedding_cache_result",
            total=len(texts),
            hits=hit_count,
            misses=len(miss_texts),
        )

        # Step 4 — embed only the misses via TEI
        miss_embeddings: list[list[float]] = []
        if miss_texts:
            miss_embeddings = await self.embed_batch(miss_texts)

            # Step 5 — persist new vectors into cache
            new_entries = []
            for i, emb in enumerate(miss_embeddings):
                idx = miss_indices[i]
                new_entries.append({
                    "text_hash": hashes[idx],
                    "text_length": len(texts[idx]),
                    "embedding_model": EMBEDDING_MODEL_NAME,
                    "embedding_dimension": EMBEDDING_DIMENSION,
                    "embedding_vector": emb,  # Keep as list[float] for proper vector type
                })
            await cache_repo.save_batch(new_entries)

        # Step 6 — merge hits + misses in original order
        result: list[list[float]] = [None] * len(texts)  # type: ignore

        # Fill cache hits
        for idx, h in enumerate(hashes):
            if h in cache_hits:
                result[idx] = cache_hits[h]

        # Fill cache misses
        for i, idx in enumerate(miss_indices):
            result[idx] = miss_embeddings[i]

        return result

    # ------------------------------------------------------------------
    # Reranker
    # ------------------------------------------------------------------
    async def rerank(self, query: str, documents: list[str]) -> list[dict]:
        """Rerank documents based on query relevance.

        Returns list of {index, score} dicts.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.reranker_url}/predict",
                json={"query": query, "documents": documents},
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()["outputs"]


# Global service instance
embedding_service = EmbeddingService()
