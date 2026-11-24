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


def is_continuation_row(row: list[str]) -> bool:
    """The overflow of the previous page's last row: first two cells empty, some other text.

    A row with an empty first cell but a text in the second is a real row (a step without a
    number), so it is never a continuation row.
    """
    return not any(c.strip() for c in row[:2]) and any(c.strip() for c in row[2:])


def looks_like_overflow(row: list[str]) -> bool:
    """A continuation row that reads as overflow text, not as a header with blank corner cells.

    At most two non-empty cells and one of them longer than 40 characters: a header cell is a
    short label (``["", "", "Q1", "Q2", "Q3"]`` is a header, not the overflow of a step).
    """
    texts = [c.strip() for c in row if c.strip()]
    return is_continuation_row(row) and len(texts) <= 2 and any(len(t) > 40 for t in texts)


def append_continuation(prev: DocElement, cur: DocElement, skip_rows: int, *,
                        stitch: bool = False) -> None:
    """Append the rows of ``cur`` to ``prev``, without its ``skip_rows`` repeated header rows.

    V2-47 (TECH-V2-ai-service §5.2): with ``stitch`` (the cleaning step; the extractor keeps
    the default), when the first appended row is a continuation row and ``prev`` has a data
    row, its text is stitched into the same columns of ``prev``'s last row instead of becoming
    a row (that row keeps its page: a step belongs to the page it starts on). A part one
    column narrower than ``prev`` is padded with an empty cell on the right.
    ``cell_spans`` of ``cur`` shift by the rows not appended; a span starting on the stitched
    row is dropped (rowspan 1) or moves to the next row with one row less. The merged value of
    a moved span belongs to the rows it still covers: it is written into the first of them
    when that cell is empty, and not appended to the row stitched into.
    """
    assert prev.rows and cur.rows
    offset = len(prev.rows)
    width = len(prev.rows[0])
    new_rows = [list(r) + [""] * (width - len(r)) for r in cur.rows[skip_rows:]]
    new_pages = (cur.row_pages or [cur.page] * len(cur.rows))[skip_rows:]
    stitched = (stitch and bool(new_rows) and offset > max(prev.header_rows, 1)
                and is_continuation_row(new_rows[0]))
    moved = {c for r, c, rs, _ in cur.cell_spans or []
             if stitched and r == skip_rows and rs > 1 and skip_rows + 1 < len(cur.rows)}
    if stitched:
        last = prev.rows[-1]
        overflow = new_rows[0]
        for col, text in enumerate(overflow):
            if text.strip() and col not in moved:
                last[col] = (last[col].rstrip() + " " + text.strip()).strip()
        new_rows, new_pages = new_rows[1:], new_pages[1:]
        for col in moved:  # the merged value is written only on its first row in the source
            if not new_rows[0][col].strip():
                new_rows[0][col] = overflow[col]
    shift = skip_rows + (1 if stitched else 0)
    prev.row_pages = (prev.row_pages or [prev.page] * offset) + new_pages
    prev.rows.extend(new_rows)
    for r, c, rs, cs in cur.cell_spans or []:
        if stitched and r == skip_rows:
            if c in moved and rs > 1:
                prev.cell_spans = (prev.cell_spans or []) + [(offset, c, rs - 1, cs)]
        elif r >= shift:
            prev.cell_spans = (prev.cell_spans or []) + [(r - shift + offset, c, rs, cs)]
    prev.page_end = cur.page_end


def continuation_rows_to_skip(prev: DocElement, cur: DocElement,
                              allow_no_header: bool) -> int | None:
    """Rows of ``cur`` to drop when it continues ``prev`` on the next page, or None.

    Page ``prev.page_end + 1`` and the same width: the header row repeats (dropped), or, with
    ``allow_no_header``, ``cur`` has no column header at all, or its first row looks like
    overflow text (``looks_like_overflow``: Docling took the overflow row for a header). With
    ``allow_no_header``, a part exactly one column narrower whose first row looks like overflow
    text also joins (Docling drops a trailing column that is empty on that page). A next-page
    table with a different header, even one with blank corner cells, is a new table (V2-47,
    TECH-V2-ai-service §5.2).
    """
    assert prev.rows and cur.rows
    if prev.page_end is None or cur.page is None or cur.page != prev.page_end + 1:
        return None
    prev_width, cur_width = len(prev.rows[0]), len(cur.rows[0])
    if prev_width == cur_width:
        if repeats_header(prev, cur):
            return 1
        if allow_no_header and (cur.header_rows == 0 or looks_like_overflow(cur.rows[0])):
            return 0
        return None
    if allow_no_header and cur_width == prev_width - 1 and looks_like_overflow(cur.rows[0]):
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
                append_continuation(last_body, el, skip, stitch=True)
                joined += 1
                continue
        kept.append(el)
        last_body = el
    doc.elements = kept
    return joined
