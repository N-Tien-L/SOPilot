"""Format dispatch. Only PDF and Markdown are accepted (PRD-V2 FR-06)."""
from __future__ import annotations

from pathlib import PurePath

from sopilot_ai.docproc.errors import ExtractionError, FailureCode
from sopilot_ai.docproc.model import StructuredDocument
from sopilot_ai.docproc.normalize import normalize_document

_PDF = {".pdf"}
_MD = {".md", ".markdown"}


def detect_file_type(filename: str) -> str:
    suffix = PurePath(filename).suffix.lower()
    if suffix in _PDF:
        return "PDF"
    if suffix in _MD:
        return "MD"
    raise ExtractionError(FailureCode.UNSUPPORTED_TYPE)


def extract(data: bytes, filename: str) -> StructuredDocument:
    """Parse ``data`` into a normalized ``StructuredDocument``.

    The type check runs before any parsing, so DOCX/TXT never reach a parser.
    """
    file_type = detect_file_type(filename)
    if file_type == "MD":
        from sopilot_ai.docproc.extract.markdown import extract_markdown

        doc = extract_markdown(data)
    else:
        from sopilot_ai.docproc.extract.pdf import extract_pdf

        doc = extract_pdf(data)
    return normalize_document(doc)
