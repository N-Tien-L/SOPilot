import hashlib
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update, text, String, cast
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.embedding_cache import EmbeddingCache


class EmbeddingCacheRepository:
    """Repository for knowledge.embedding_cache operations.

    Provides batch lookup and batch upsert to minimise round-trips
    when processing documents with many chunks.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def hash_text(text: str) -> str:
        """Compute a deterministic SHA-256 hash for a chunk's content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def lookup_batch(
        self,
        text_hashes: list[str],
        embedding_model: str,
    ) -> dict[str, list[float]]:
        """Look up cached embeddings for a list of text hashes.

        Returns a dict mapping text_hash → embedding_vector for every
        cache hit.  Cache misses are simply absent from the dict.
        """
        if not text_hashes:
            return {}

        result = await self.session.execute(
            text("""
                SELECT text_hash, embedding_vector
                FROM knowledge.embedding_cache
                WHERE text_hash = ANY(:hashes)
                  AND embedding_model = :model
            """),
            {"hashes": text_hashes, "model": embedding_model}
        )

        cache_hits: dict[str, list[float]] = {}
        for row in result.all():
            # Convert string representation back to list[float] for consistency
            vector_str = row.embedding_vector
            if isinstance(vector_str, str):
                # Parse the string representation back to list
                import ast
                cache_hits[row.text_hash] = ast.literal_eval(vector_str)
            else:
                # If it's already a list (shouldn't happen but just in case)
                cache_hits[row.text_hash] = list(vector_str)

        if cache_hits:
            hash_tuple = tuple(cache_hits.keys())
            await self.session.execute(
                text("""
                    UPDATE knowledge.embedding_cache
                    SET usage_count = usage_count + 1, last_used_at = NOW()
                    WHERE text_hash = ANY(:hashes)
                      AND embedding_model = :model
                """),
                {"hashes": hash_tuple, "model": embedding_model}
            )

        return cache_hits

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def save_batch(
        self,
        entries: list[dict],
    ) -> None:
        """Persist new embeddings into the cache.

        Each entry must contain:
          - text_hash: str
          - text_length: int
          - embedding_model: str
          - embedding_dimension: int
          - embedding_vector: list[float]

        Uses ON CONFLICT … DO UPDATE so repeated calls are safe.
        """
        if not entries:
            return

        # Convert embedding vectors to string representation for the database
        processed_entries = []
        for entry in entries:
            processed_entry = entry.copy()
            emb = processed_entry.get('embedding_vector')
            
            # Convert list[float] to string representation for pgvector
            if isinstance(emb, list):
                processed_entry['embedding_vector'] = str(emb)
            elif isinstance(emb, str) and not emb.startswith('['):
                # Try to normalize string if it's not already in PG vector format
                try:
                    import ast
                    parsed = ast.literal_eval(emb)
                    if isinstance(parsed, list):
                        processed_entry['embedding_vector'] = str(parsed)
                except:
                    pass
                    
            processed_entries.append(processed_entry)
        
        await self.session.execute(
            text("""
                INSERT INTO knowledge.embedding_cache (
                    text_hash, text_length,
                    embedding_model, embedding_dimension,
                    embedding_vector,
                    usage_count, last_used_at
                ) VALUES (
                    :text_hash, :text_length,
                    :embedding_model, :embedding_dimension,
                    :embedding_vector,
                    1, NOW()
                )
                ON CONFLICT (text_hash, embedding_model) DO UPDATE SET
                    usage_count   = knowledge.embedding_cache.usage_count + 1,
                    last_used_at  = NOW()
            """),
            processed_entries,
        )
