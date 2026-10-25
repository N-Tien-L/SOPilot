"""Pure document-processing package: bytes in, structured document and canonical Markdown out.

No database, web or provider imports belong here (TECH-V2-ai-service §1.1).
"""
from sopilot_ai.docproc.errors import ExtractionError, FailureCode
from sopilot_ai.docproc.extract import extract
from sopilot_ai.docproc.model import DocElement, RenderedDocument, StructuredDocument
from sopilot_ai.docproc.render import NORMALIZER_VERSION, render

__all__ = [
    "NORMALIZER_VERSION",
    "DocElement",
    "ExtractionError",
    "FailureCode",
    "RenderedDocument",
    "StructuredDocument",
    "extract",
    "render",
]
