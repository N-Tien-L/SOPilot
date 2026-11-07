"""Canonical Markdown renderer with source offsets (TECH-V2-ai-service §5.2).

Deterministic: the same ``StructuredDocument`` always renders to the same string. Offsets are
Python string indices (Unicode code points) on ``markdown``; ``utf16_offset`` converts them for
browsers. Only ``content`` and ``figure_text`` elements are rendered.
"""
from __future__ import annotations

import re

from sopilot_ai.docproc.model import DocElement, PageSpan, RenderedDocument, StructuredDocument

NORMALIZER_VERSION = "2"  # 2: figure_text elements are rendered

_RENDERED_ROLES = ("content", "figure_text")

_BLOCK_SEP = "\n\n"


def _escape_cell(cell: str) -> str:
    backslash = chr(92)
    escaped = cell.replace(backslash, backslash * 2).replace("|", backslash + "|")
    return escaped.replace(chr(10), " ")


def _render_table(el: DocElement) -> tuple[str, list[tuple[int, int]]]:
    assert el.rows
    width = len(el.rows[0])
    lines: list[str] = []
    spans: list[tuple[int, int]] = []
    pos = 0

    def row_line(cells: list[str]) -> str:
        return "| " + " | ".join(_escape_cell(c) for c in cells) + " |"

    header = row_line(el.rows[0])
    lines.append(header)
    spans.append((pos, pos + len(header)))
    pos += len(header) + 1
    sep = "| " + " | ".join(["---"] * width) + " |"
    lines.append(sep)
    pos += len(sep) + 1
    for row in el.rows[1:]:
        line = row_line(row)
        lines.append(line)
        spans.append((pos, pos + len(line)))
        pos += len(line) + 1
    return "\n".join(lines), spans


def _render_code(el: DocElement) -> str:
    longest = max((len(m) for m in re.findall(r"`+", el.text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{el.text}\n{fence}"


def _render_block(el: DocElement) -> tuple[str, list[tuple[int, int]] | None]:
    if el.kind == "heading":
        level = min(max(el.level or 1, 1), 6)
        return f"{'#' * level} {el.text}", None
    if el.kind == "list_item":
        indent = "  " * max((el.level or 1) - 1, 0)
        marker = f"{el.number} " if el.number else "- "
        return f"{indent}{marker}{el.text}", None
    if el.kind == "table":
        return _render_table(el)
    if el.kind == "code":
        return _render_code(el), None
    return el.text, None


def render(doc: StructuredDocument) -> RenderedDocument:
    parts: list[str] = []
    out: list[DocElement] = []
    pos = 0
    # (page, char_start) markers in document order, PDF only.
    markers: list[tuple[int, int]] = []

    for el in doc.elements:
        if el.role not in _RENDERED_ROLES or el.kind == "page_break":
            out.append(el.model_copy(update={"char_start": None, "char_end": None,
                                             "row_spans": None}))
            continue
        block, rel_spans = _render_block(el)
        if not block.strip():
            out.append(el.model_copy(update={"char_start": None, "char_end": None,
                                             "row_spans": None}))
            continue
        if parts:
            pos += len(_BLOCK_SEP)
        start, end = pos, pos + len(block)
        row_spans = [(start + a, start + b) for a, b in rel_spans] if rel_spans else None
        out.append(el.model_copy(update={"char_start": start, "char_end": end,
                                         "row_spans": row_spans}))
        if doc.file_type == "PDF" and el.page is not None:
            markers.append((el.page, start))
            if el.kind == "table" and el.row_pages and row_spans:
                for page, (row_start, _) in zip(el.row_pages[0:], row_spans, strict=False):
                    markers.append((page, row_start))
        parts.append(block)
        pos = end

    markdown = _BLOCK_SEP.join(parts)
    return RenderedDocument(
        markdown=markdown,
        elements=out,
        page_index=_build_page_index(markers, len(markdown)),
        normalizer_version=NORMALIZER_VERSION,
    )


def _build_page_index(markers: list[tuple[int, int]], total: int) -> list[PageSpan]:
    """Contiguous, non-overlapping page ranges; a range runs to the next page's start."""
    changes: list[tuple[int, int]] = []
    for page, start in markers:
        if not changes or changes[-1][0] != page:
            changes.append((page, start))
    spans: list[PageSpan] = []
    for i, (page, start) in enumerate(changes):
        end = changes[i + 1][1] if i + 1 < len(changes) else total
        spans.append(PageSpan(page=page, char_start=start, char_end=end))
    return spans


def utf16_offset(text: str, index: int) -> int:
    """Convert a code-point index into a UTF-16 code-unit index (browser string offsets)."""
    return len(text[:index].encode("utf-16-le")) // 2
