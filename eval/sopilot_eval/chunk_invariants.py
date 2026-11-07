"""V2-22: offset and page invariants of chunks over a rendered, cleaned document.

Pure checks on plain dicts (``RenderedDocument.elements`` and ``Chunk`` dumped with
``model_dump()``), so they run without ai-service installed. ``check_chunks_corpus.py`` feeds
them the V2-19 corpus.

Invariants (name: rule):

* ``offsets``: ``0 <= char_start < char_end <= len(markdown)``.
* ``substring``: a ``TEXT`` chunk's ``content`` equals ``markdown[char_start:char_end]``. A
  ``TABLE`` chunk either equals that slice, or is a row-cut part: ``char_start`` is the start of
  a source row and ``char_end`` the end of a later (or the same) row of one table, and
  ``content`` ends with the slice (the column header is repeated in front); a row that alone is
  over budget may be split, then ``content`` lies inside that one row's span.
* ``procedure_row``: a ``PROCEDURE_STEP`` chunk's ``[char_start, char_end)`` equals
  ``row_spans[i]`` of a source table and ``page_start == page_end == row_pages[i]`` (the
  table's ``page`` when ``row_pages`` is absent).
* ``page_order``: ``page_start`` and ``page_end`` are both null or both set, and
  ``page_start <= page_end``.
* ``page_source`` (not for ``PROCEDURE_STEP``): ``page_start``/``page_end`` equal the smallest
  page and the largest end page of the source units the chunk overlaps. A unit is a table row
  (``row_spans[i]``, page ``row_pages[i]``) or any other rendered element (``page``,
  ``page_end``). No paged unit means both must be null.
* ``multi_page_table``: a chunk that overlaps rows of one table lying on more than one page has
  ``page_end > page_start``.
* ``token_budget``: ``token_count <= max_tokens`` when a budget is given.
"""

from __future__ import annotations

from collections import Counter

INVARIANTS = ("offsets", "substring", "procedure_row", "page_order", "page_source",
              "multi_page_table", "token_budget")
_SNIPPET = 80


def _units(elements: list[dict]) -> tuple[list[tuple], list[dict]]:
    """``(start, end, page, page_end, table_index, row)`` per unit; rendered tables."""
    units, tables = [], []
    for el in elements:
        if el.get("char_start") is None or el.get("char_end") is None:
            continue
        spans = el.get("row_spans") if el.get("kind") == "table" else None
        if spans:
            index = len(tables)
            tables.append(el)
            row_pages = el.get("row_pages")
            for row, (start, end) in enumerate(spans):
                page = row_pages[row] if row_pages else el.get("page")
                units.append((start, end, page, page, index, row))
        else:
            page = el.get("page")
            units.append((el["char_start"], el["char_end"], page,
                          el.get("page_end") or page, None, None))
    return units, tables


def _row_page(table: dict, row: int):
    row_pages = table.get("row_pages")
    return row_pages[row] if row_pages else table.get("page")


def _table_part_ok(markdown: str, tables: list[dict], chunk: dict) -> bool:
    start, end, content = chunk["char_start"], chunk["char_end"], chunk["content"]
    rows_text = markdown[start:end]
    for table in tables:
        spans = [tuple(s) for s in table["row_spans"]]
        starts = [i for i, s in enumerate(spans) if s[0] == start]
        ends = [i for i, s in enumerate(spans) if s[1] == end]
        if not starts or not ends:
            continue
        if starts[0] <= ends[0] and content.endswith(rows_text):
            return True
        if starts[0] == ends[0] and content and content in rows_text:
            return True  # an oversized row split into pieces
    return False


def continuation_blockers(elements: list[dict]) -> Counter:
    """Why the last body table of page p and the first body table of page p+1 were not joined.

    Mirrors the extractor's ``_merge_tables`` conditions on the extracted elements (before
    cleaning): the previous body element must be that table, the next body element must be the
    continuation, widths must match and the header row must repeat. ``would_merge`` counts
    pairs that pass every condition (they should already be one table).
    """
    by_page: dict[int, list[dict]] = {}
    for el in elements:
        if el.get("role") == "content" and el.get("kind") != "page_break" \
                and el.get("page") is not None:
            by_page.setdefault(el["page"], []).append(el)
    reasons: Counter = Counter()
    for page, items in by_page.items():
        after = by_page.get(page + 1, [])
        prev = next((e for e in reversed(items) if e["kind"] == "table"), None)
        cur = next((e for e in after if e["kind"] == "table"), None)
        if prev is None or cur is None:
            continue
        if prev is not items[-1]:
            reasons["body_text_after_table"] += 1
        elif cur is not after[0]:
            reasons["body_element_before_next_table"] += 1
        elif len(prev["rows"][0]) != len(cur["rows"][0]):
            reasons["width_differs"] += 1
        elif [c.strip() for c in prev["rows"][0]] != [c.strip() for c in cur["rows"][0]]:
            reasons["header_row_not_repeated"] += 1
        else:
            reasons["would_merge"] += 1
    return reasons


def check_chunks(markdown: str, elements: list[dict], chunks: list[dict],
                 max_tokens: int | None = None, doc_id: str = "") -> dict:
    """Count checks and violations per invariant; keep the violating chunks as examples."""
    units, tables = _units(elements)
    checked: Counter = Counter()
    violations: Counter = Counter()
    examples: list[dict] = []
    multi_page_chunks = 0

    def fail(name: str, index: int, chunk: dict, detail: str) -> None:
        violations[name] += 1
        content = " ".join(chunk["content"].split())
        examples.append({"doc_id": doc_id, "invariant": name, "chunk": index,
                         "kind": chunk["kind"], "char_start": chunk["char_start"],
                         "char_end": chunk["char_end"], "page_start": chunk["page_start"],
                         "page_end": chunk["page_end"], "detail": detail,
                         "content": content[:_SNIPPET]})

    for index, chunk in enumerate(chunks):
        start, end, kind = chunk["char_start"], chunk["char_end"], chunk["kind"]
        page_start, page_end = chunk["page_start"], chunk["page_end"]
        checked["offsets"] += 1
        if not 0 <= start < end <= len(markdown):
            fail("offsets", index, chunk, f"markdown length {len(markdown)}")
            continue
        if kind in ("TEXT", "TABLE"):
            checked["substring"] += 1
            exact = markdown[start:end] == chunk["content"]
            if not exact and (kind == "TEXT" or not _table_part_ok(markdown, tables, chunk)):
                fail("substring", index, chunk, "content is not the markdown slice")
        checked["page_order"] += 1
        if (page_start is None) != (page_end is None) or (
                page_start is not None and page_start > page_end):
            fail("page_order", index, chunk, "page_start/page_end inconsistent")
        if kind == "PROCEDURE_STEP":
            checked["procedure_row"] += 1
            pages = [_row_page(t, r) for t in tables
                     for r, s in enumerate(t["row_spans"]) if tuple(s) == (start, end)]
            if not pages:
                fail("procedure_row", index, chunk, "offsets are not a source row span")
            elif not (page_start == page_end and page_start in pages):
                fail("procedure_row", index, chunk, f"source row page {pages[0]}")
        else:
            checked["page_source"] += 1
            covered = [u for u in units if u[0] < end and u[1] > start]
            paged = [u for u in covered if u[2] is not None]
            expected = (min(u[2] for u in paged), max(u[3] for u in paged)) if paged \
                else (None, None)
            if (page_start, page_end) != expected:
                fail("page_source", index, chunk, f"source pages {expected[0]}..{expected[1]}")
        table_pages: dict[int, set] = {}
        for u in units:
            if u[4] is not None and u[0] < end and u[1] > start and u[2] is not None:
                table_pages.setdefault(u[4], set()).add(u[2])
        if any(len(p) > 1 for p in table_pages.values()):
            multi_page_chunks += 1
            checked["multi_page_table"] += 1
            if page_start is None or not page_end > page_start:
                fail("multi_page_table", index, chunk, "covers table rows on several pages")
        if max_tokens is not None:
            checked["token_budget"] += 1
            if chunk["token_count"] > max_tokens:
                fail("token_budget", index, chunk, f"{chunk['token_count']} > {max_tokens}")
    return {
        "chunks": len(chunks),
        "by_kind": dict(Counter(c["kind"] for c in chunks)),
        "multi_page_table_chunks": multi_page_chunks,
        "checked": {k: checked[k] for k in INVARIANTS},
        "violations": {k: violations[k] for k in INVARIANTS},
        "examples": examples,
    }
