"""Document family detection and structure-aware chunking (V2-22)."""
from sopilot_ai.docproc.chunk.chunker import (
    Chunk,
    ChunkConfig,
    Chunker,
    chunk_document,
    index_prefix,
)
from sopilot_ai.docproc.chunk.family import DocFamily, detect_family

__all__ = [
    "Chunk",
    "ChunkConfig",
    "Chunker",
    "DocFamily",
    "chunk_document",
    "detect_family",
    "index_prefix",
]
