"""Joining a table that continues on the next page (TECH-V2-ai-service §5.2).

The extractor joins the simple case (the next page starts with the same table and repeats its
header row). The cleaning step joins again after the page frame is marked, because a header
drawn as a table at the top of every page sits between the two parts until then (V2-21/V2-22).
"""
from __future__ import annotations

from sopilot_ai.docproc.model import DocElement, StructuredDocument

_PASSTHROUGH_ROLES = ("header", "footer", "boilerplate")


def repeats_header(prev: DocElement, cur: DocElement) -> bool:
    assert prev.rows and cur.rows
    return [c.strip() for c in prev.rows[0]] == [c.strip() for c in cur.rows[0]]


def append_continuation(prev: DocElement, cur: DocElement, skip_rows: int) -> None:
    """Append the rows of ``cur`` to ``prev``, without its ``skip_rows`` repeated header rows."""
    assert prev.rows and cur.rows
    offset = len(prev.rows)
    prev.rows.extend(cur.rows[skip_rows:])
    prev.row_pages = ((prev.row_pages or [prev.page] * offset)
                      + (cur.row_pages or [cur.page] * len(cur.rows))[skip_rows:])
    for r, c, rs, cs in cur.cell_spans or []:
        if r >= skip_rows:
            prev.cell_spans = (prev.cell_spans or []) + [(r - skip_rows + offset, c, rs, cs)]
    prev.page_end = cur.page_end


def continuation_rows_to_skip(prev: DocElement, cur: DocElement,
                              allow_no_header: bool) -> int | None:
    """Rows of ``cur`` to drop when it continues ``prev`` on the next page, or None.

    Same width and page ``prev.page_end + 1``; the header row repeats (dropped), or, with
    ``allow_no_header``, ``cur`` has no column header at all (a continuation that does not
    repeat it). A next-page table with a different header is a new table.
    """
    assert prev.rows and cur.rows
    if prev.page_end is None or cur.page is None or cur.page != prev.page_end + 1:
        return None
    if len(prev.rows[0]) != len(cur.rows[0]):
        return None
    if repeats_header(prev, cur):
        return 1
    if allow_no_header and cur.header_rows == 0:
        return 0
    return None


def join_continued_tables(doc: StructuredDocument) -> int:
    """Join body tables split by a page break; frame elements between them are passed over.

    Runs after header/footer marking. Two body tables are joined when nothing but frame lies
    between them (so the first ends its page and the second starts the next) and
    ``continuation_rows_to_skip`` accepts the pair. Returns the number of joins.
    """
    joined = 0
    kept: list[DocElement] = []
    last_body: DocElement | None = None
    for el in doc.elements:
        if el.kind == "page_break" or el.role in _PASSTHROUGH_ROLES:
            kept.append(el)
            continue
        if (el.kind == "table" and el.role == "content" and last_body is not None
                and last_body.kind == "table" and last_body.role == "content"):
            skip = continuation_rows_to_skip(last_body, el, allow_no_header=True)
            if skip is not None:
                append_continuation(last_body, el, skip)
                joined += 1
                continue
        kept.append(el)
        last_body = el
    doc.elements = kept
    return joined
