"""Cleaning step (V2-21): drop the frame, keep the body, extract SOP metadata, add warnings."""
from __future__ import annotations

from sopilot_ai.docproc.clean.boilerplate import (
    collect_boilerplate,
    mark_frame_blocks,
    mark_repeated_header_footer,
)
from sopilot_ai.docproc.clean.metadata import extract_metadata
from sopilot_ai.docproc.clean.model import (
    BoilerplateBlock,
    CleanConfig,
    CleanResult,
    ExtractedMeta,
    ExtractionWarning,
)
from sopilot_ai.docproc.clean.warnings import build_warnings
from sopilot_ai.docproc.model import StructuredDocument
from sopilot_ai.docproc.tokens import Tokenizer


def clean_document(
    doc: StructuredDocument,
    config: CleanConfig | None = None,
    tokenizer: Tokenizer | None = None,
) -> CleanResult:
    """Mark frame elements (``role``), extract metadata from them and report warnings.

    Metadata is read before the frame is dropped from the rendered Markdown. The returned
    document keeps every element; ``render`` skips the ones whose role is not content.
    """
    config = config or CleanConfig()
    work = doc.model_copy(deep=True)
    mark_repeated_header_footer(work, config)
    kinds = mark_frame_blocks(work)
    boilerplate = collect_boilerplate(work, kinds)
    meta = extract_metadata(work)
    warnings = build_warnings(work, len(boilerplate), config, tokenizer)
    return CleanResult(document=work, boilerplate=boilerplate, meta=meta, warnings=warnings)


__all__ = [
    "BoilerplateBlock",
    "CleanConfig",
    "CleanResult",
    "ExtractedMeta",
    "ExtractionWarning",
    "clean_document",
]
