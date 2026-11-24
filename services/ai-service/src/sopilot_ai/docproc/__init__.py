"""Pure document-processing package: bytes in, structured document and canonical Markdown out.

No database, web or provider imports belong here (TECH-V2-ai-service §1.1).
"""
from sopilot_ai.docproc.chunk import Chunk, ChunkConfig, DocFamily, chunk_document, detect_family
from sopilot_ai.docproc.clean import CleanConfig, CleanResult, clean_document
from sopilot_ai.docproc.errors import ExtractionError, FailureCode
from sopilot_ai.docproc.extract import extract
from sopilot_ai.docproc.model import DocElement, RenderedDocument, StructuredDocument
from sopilot_ai.docproc.render import NORMALIZER_VERSION, render
from sopilot_ai.docproc.tokens import Tokenizer

__all__ = [
    "NORMALIZER_VERSION",
    "Chunk",
    "ChunkConfig",
    "CleanConfig",
    "CleanResult",
    "DocElement",
    "DocFamily",
    "ExtractionError",
    "FailureCode",
    "RenderedDocument",
    "StructuredDocument",
    "Tokenizer",
    "chunk_document",
    "clean_document",
    "detect_family",
    "extract",
    "render",
]
