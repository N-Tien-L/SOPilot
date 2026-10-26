"""Extraction warnings (TECH-V2-ai-service §5.3a). Concrete signals only, no confidence score."""
from __future__ import annotations

import re
from collections import Counter

from sopilot_ai.docproc.clean.model import (
    BOILERPLATE_REMOVED,
    CONVERTER_WARNING,
    NO_HEADINGS_DETECTED,
    PAGES_WITHOUT_TEXT,
    UNMAPPED_GLYPHS,
    CleanConfig,
    ExtractionWarning,
)
from sopilot_ai.docproc.model import DocElement, StructuredDocument
from sopilot_ai.docproc.tokens import Tokenizer

_BAD_GLYPHS = re.compile(r"�|\(cid:\d+\)|[-]")
_BODY_ROLES = ("content", "figure_text")


def _page_chars(doc: StructuredDocument) -> Counter[int]:
    """Characters of body text per page (a multi-page table is split by ``row_pages``)."""
    chars: Counter[int] = Counter()
    for el in doc.elements:
        if el.role not in _BODY_ROLES or el.page is None:
            continue
        if el.kind == "table" and el.rows and el.row_pages:
            for page, row in zip(el.row_pages, el.rows, strict=True):
                chars[page] += sum(len(c.strip()) for c in row)
        elif el.kind == "table" and el.rows:
            chars[el.page] += sum(len(c.strip()) for row in el.rows for c in row)
        else:
            for page in range(el.page, (el.page_end or el.page) + 1):
                chars[page] += len(el.text.strip())
    return chars


def _glyph_hits(el: DocElement) -> int:
    texts = [c for row in el.rows for c in row] if el.kind == "table" and el.rows else [el.text]
    return sum(len(_BAD_GLYPHS.findall(t)) for t in texts)


def build_warnings(
    doc: StructuredDocument,
    removed_blocks: int,
    config: CleanConfig,
    tokenizer: Tokenizer | None = None,
) -> list[ExtractionWarning]:
    out: list[ExtractionWarning] = []
    body = [el for el in doc.elements if el.role in _BODY_ROLES]

    if doc.file_type == "PDF" and doc.page_count:
        chars = _page_chars(doc)
        empty = [p for p in range(1, doc.page_count + 1)
                 if chars.get(p, 0) < config.page_min_chars]
        if empty:
            out.append(ExtractionWarning(code=PAGES_WITHOUT_TEXT, pages=empty))

    glyph_pages: set[int] = set()
    glyph_count = 0
    for el in body:
        hits = _glyph_hits(el)
        if hits:
            glyph_count += hits
            if el.page is not None:
                glyph_pages.update(range(el.page, (el.page_end or el.page) + 1))
    if glyph_count:
        out.append(ExtractionWarning(code=UNMAPPED_GLYPHS, pages=sorted(glyph_pages) or None,
                                     count=glyph_count))

    if not any(el.kind == "heading" for el in body) and _is_long(doc, body, config, tokenizer):
        out.append(ExtractionWarning(code=NO_HEADINGS_DETECTED))

    if removed_blocks:
        out.append(ExtractionWarning(code=BOILERPLATE_REMOVED, count=removed_blocks))

    for note in doc.converter_warnings:
        out.append(ExtractionWarning(code=CONVERTER_WARNING, kind=note.get("kind"),
                                     pages=note.get("pages") or None))
    return out


def _is_long(doc: StructuredDocument, body: list[DocElement], config: CleanConfig,
             tokenizer: Tokenizer | None) -> bool:
    if doc.file_type == "PDF":
        return bool(doc.page_count and doc.page_count > 1)
    if tokenizer is None:
        return False
    text = "\n".join(el.text for el in body if el.kind != "table")
    return tokenizer.count(text) > config.max_tokens
