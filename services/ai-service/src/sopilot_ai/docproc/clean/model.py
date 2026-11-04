"""Result types of the cleaning step (TECH-V2-ai-service §5.3, §5.3a)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from sopilot_ai.docproc.model import StructuredDocument

PAGES_WITHOUT_TEXT = "PAGES_WITHOUT_TEXT"
UNMAPPED_GLYPHS = "UNMAPPED_GLYPHS"
NO_HEADINGS_DETECTED = "NO_HEADINGS_DETECTED"
BOILERPLATE_REMOVED = "BOILERPLATE_REMOVED"
CONVERTER_WARNING = "CONVERTER_WARNING"


@dataclass(frozen=True)
class CleanConfig:
    """Starting values, to be settled on the V2-19 corpus."""

    header_footer_min_pages: int = 3  # SOPILOT_HEADER_FOOTER_MIN_PAGES
    header_footer_ratio: float = 0.4
    page_min_chars: int = 20  # SOPILOT_PAGE_MIN_CHARS
    max_tokens: int = 512  # chunking.max_tokens, for NO_HEADINGS_DETECTED on long Markdown

    @classmethod
    def from_env(cls) -> CleanConfig:
        defaults = cls()
        return cls(
            header_footer_min_pages=int(os.environ.get(
                "SOPILOT_HEADER_FOOTER_MIN_PAGES", defaults.header_footer_min_pages)),
            page_min_chars=int(os.environ.get("SOPILOT_PAGE_MIN_CHARS", defaults.page_min_chars)),
        )


class BoilerplateBlock(BaseModel):
    """One removed block: ``extracted_documents.boilerplate`` holds ``{kind, page, text}``."""

    kind: str
    page: int | None = None
    text: str


class ExtractedMeta(BaseModel):
    """SOP metadata found in the frame, sent to core-api in the ``READY`` callback."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    doc_code: str | None = None
    revision_label: str | None = None
    issue_date: str | None = None
    effective_date: str | None = None
    approved_by: str | None = None


class ExtractionWarning(BaseModel):
    """A concrete signal about the extraction; there is no aggregate confidence score."""

    code: str
    pages: list[int] | None = None
    count: int | None = None
    kind: str | None = None


class CleanResult(BaseModel):
    document: StructuredDocument
    boilerplate: list[BoilerplateBlock]
    meta: ExtractedMeta
    warnings: list[ExtractionWarning]
