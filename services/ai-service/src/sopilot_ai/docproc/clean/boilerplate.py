"""Frame detection: repeated page header/footer and Vietnamese/English frame blocks (§5.3).

Detection only changes ``DocElement.role``; nothing is deleted, so the renderer skips the frame
and ``collect_boilerplate`` can still list it. Rules are deliberately narrow: a block is marked
only when its position and wording both say "frame", because a wrongly removed block is lost
from the index.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from sopilot_ai.docproc.clean.model import BoilerplateBlock, CleanConfig
from sopilot_ai.docproc.model import DocElement, StructuredDocument

# Elements per page edge whose text is counted as a header/footer occurrence. The frame itself is
# then the run of repeated elements from the edge inward, of any length (a label/value header
# such as "SOP Number:" / "21301" / "Revision:" / "07" spans many elements).
_EDGE_WINDOW = 10
_MAX_FRAME_CHARS = 200  # a longer block is a paragraph, never a header/footer line
_MAX_FRAME_TABLE_ROWS = 6  # a page header drawn as a table is a small grid of short cells
_FRAME_TABLE_SHARE = 0.6  # share of its lettered cells that must repeat on other pages
_MAX_FRAME_LABEL = 60  # longest non-repeating cell a header grid may hold
_LEADING_ELEMENTS = 12  # national motto / document number sit at the top of the first page
_TRAILING_ELEMENTS = 8  # signature block and recipients sit at the end
_MAX_SIGNATURE_LINE = 80
_MAX_META_LINE = 80
_MAX_RECIPIENT_ITEMS = 30


def fold(text: str) -> str:
    """Lowercase, strip diacritics (``đ`` -> ``d``) for wording rules that ignore accent style."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def element_text(el: DocElement) -> str:
    if el.kind == "table" and el.rows:
        return "\n".join(" | ".join(row) for row in el.rows)
    return el.text


def _in_body(el: DocElement) -> bool:
    return el.role == "content"


_OUTLINE_NUMBER = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+(?=[^\W\d_])")


def _repeat_key(text: str) -> str:
    """Digits masked (page numbers, dates), except a leading section number: "1.1 General" and
    "2.1 General" are two headings, not one repeated line."""
    text = " ".join(text.lower().split())
    outline = _OUTLINE_NUMBER.match(text)
    head = outline.group(0) if outline else ""
    return head + re.sub(r"\d+", "#", text[len(head):])


_LETTER = re.compile(r"[^\W\d_]")
# "Label: value" on a frame line; the value may change (a date filled in later, "…/5/2021").
_LABELLED = re.compile(r"^([^\W\d_][^:：]{1,38}[:：])\s*\S.{0,40}$")


def _line_keys(text: str) -> list[str]:
    """Repeat key of a line, plus the key of its label when it is a short "Label: value"."""
    key = _repeat_key(text)
    labelled = _LABELLED.match(key)
    return [key, labelled.group(1)] if labelled else [key]


def _frame_pieces(el: DocElement) -> list[tuple[int, list[str]]] | None:
    """Repeat keys of an element that may be a page header/footer, or None if it cannot be.

    One ``(row, alternative keys)`` pair per text unit. A line element is one unit. A
    small table of short cells has one unit per non-empty cell, keyed by the cell and by the cell
    joined with its non-empty neighbour in the row, because the extractor splits the same header
    differently from page to page (a "Revision: 07" line on one page, cells "Revision:" | "07"
    on the next).
    """
    if el.kind in ("paragraph", "heading", "list_item"):
        text = el.text.strip()
        return [(0, _line_keys(text))] if text and len(text) <= _MAX_FRAME_CHARS else None
    if el.kind != "table" or not el.rows or len(el.rows) > _MAX_FRAME_TABLE_ROWS:
        return None
    groups: list[tuple[int, list[str]]] = []
    for r, row in enumerate(el.rows):
        cells = [c.strip() for c in row if c.strip()]
        if any(len(c) > _MAX_FRAME_CHARS for c in cells):
            return None
        for i, cell in enumerate(cells):
            keys = _line_keys(cell)
            if i > 0:
                keys.append(_repeat_key(f"{cells[i - 1]} {cell}"))
            if i + 1 < len(cells):
                keys.append(_repeat_key(f"{cell} {cells[i + 1]}"))
            groups.append((r, keys))
    return groups or None


def mark_repeated_header_footer(doc: StructuredDocument, config: CleanConfig) -> None:
    """The run of repeated elements at each page edge becomes header/footer.

    A text (digits masked) is "repeated" when it occurs near a page edge on at least
    ``max(header_footer_min_pages, header_footer_ratio * page_count)`` pages. On each page the
    frame is the run of repeated elements from the top edge down and from the bottom edge up;
    the run stops at the first element that is not repeated, so a repeated line inside the body
    is kept. A table counts as repeated when it is small and most of its lettered cells repeat.
    Skipped below ``header_footer_min_pages``: with one or two pages every edge line would
    repeat and the title and last paragraph would be removed.
    """
    if doc.file_type != "PDF" or not doc.page_count:
        return
    if doc.page_count < config.header_footer_min_pages:
        return
    by_page: dict[int, list[int]] = defaultdict(list)
    for index, el in enumerate(doc.elements):
        if el.page is not None and _in_body(el) and el.kind != "page_break":
            by_page[el.page].append(index)
    first_heading = next((i for i, el in enumerate(doc.elements)
                          if el.kind == "heading" and _in_body(el)), None)
    pieces = {i: _frame_pieces(doc.elements[i]) for ids in by_page.values() for i in ids}
    pages_of: dict[str, set[int]] = defaultdict(set)
    for page, indexes in by_page.items():
        edge = set(indexes[:_EDGE_WINDOW]) | set(indexes[-_EDGE_WINDOW:])
        for index in edge:
            for _, group in pieces[index] or []:
                for key in group:
                    pages_of[key].add(page)
    needed = max(config.header_footer_min_pages, config.header_footer_ratio * doc.page_count)

    def unit_repeats(group: list[str]) -> bool:
        return any(len(pages_of[key]) >= needed for key in group)

    def repeated(index: int) -> bool:
        groups = pieces[index]
        if not groups:
            return False
        if doc.elements[index].kind != "table":
            return unit_repeats(groups[0][1])
        # A header grid: most lettered cells repeat, every lettered row has a repeating cell and
        # the cells that do not repeat are short (split labels such as "TRA NINH BÌNH ...").
        # A body table whose column titles repeat on each page fails on its data rows.
        lettered = [(r, keys) for r, keys in groups if _LETTER.search(keys[0])]
        if not lettered:
            return False
        hits = [unit_repeats(keys) for _, keys in lettered]
        if sum(hits) < _FRAME_TABLE_SHARE * len(lettered):
            return False
        rows_hit = {r for (r, _), hit in zip(lettered, hits, strict=True) if hit}
        if {r for r, _ in lettered} - rows_hit:
            return False
        return all(hit or len(keys[0]) <= _MAX_FRAME_LABEL
                   for (_, keys), hit in zip(lettered, hits, strict=True))

    for indexes in by_page.values():
        top = 0
        while top < len(indexes) and repeated(indexes[top]):
            top += 1
        bottom = len(indexes)
        while bottom > top and repeated(indexes[bottom - 1]):
            bottom -= 1
        for position, index in enumerate(indexes):
            if index == first_heading or top <= position < bottom:
                continue
            doc.elements[index].role = "header" if position < top else "footer"  # type: ignore[assignment]


_MOTTO = (
    re.compile(r"cong hoa xa hoi chu nghia viet nam"),
    re.compile(r"doc lap\s*[-–—]+\s*tu do\s*[-–—]+\s*hanh phuc"),
)
_DOC_NUMBER = re.compile(
    r"^(so|no\.?|ma so|ma hieu|so hieu|document no\.?|doc\.? no\.?)\s*[:：.]\s*\S")
_DOC_META_LINE = re.compile(
    r"^(lan ban hanh|lan sua doi|lan soat xet|ngay hieu luc|ngay ban hanh|phien ban|revision"
    r"|rev\.?|issue(?: no\.?| date)?|effective(?: date)?|version)\s*[:：.]?\s*\S")
_RECIPIENTS = re.compile(r"^(noi nhan|recipients?|distribution)\s*[:：]?")
_SIGNATURE_START = re.compile(r"^((tm|kt|tuq|tl)\.\s|nguoi ky\b)")
_SIGNATURE_WORD = re.compile(
    r"^\(?\s*(ky ten|ky va ghi ro ho ten|signature|signed)\s*\)?\s*[:.]?$")

_APPROVAL_TERMS = (("soan thao", "soat xet", "phe duyet"),
                   ("prepared", "reviewed", "approved"),
                   ("nguoi soan", "nguoi soat", "nguoi phe"))
# Row/column labels of a sign-off grid ("Họ tên", "Chữ ký", "Name", "Signature", "Date").
_SIGN_OFF_LABEL = re.compile(
    r"\b(ho (va )?ten|chu ky|chuc vu|ngay|name|signature|sign|title|position|date)\b")
_MAX_LABEL_CELL = 40
_MAX_UNLABELLED_APPROVAL_ROWS = 3
_INDEX_HEAD = re.compile(r"^(s?tt|so tt|no\.?|#|item)$")
# Revision history: the first column names the revision (a change request, revision number or
# "History"), another column its date or description. "Lần ban hành" / "Ngày ban hành" alone
# describe an issued document (a document register), not a revision of this one.
_REVISION_HEAD = re.compile(r"sua doi|revision|history|change|\brev\b")
_REVISION_COLUMN = re.compile(r"ngay|date|noi dung|description|content|nguoi|by")
_REVISION_TITLE = re.compile(
    r"^(bang )?(theo doi )?(sua doi|revision history|change history|lich su sua doi)")


def _has_index_column(el: DocElement) -> bool:
    """First column numbers the rows (STT / No. / 1, 2, 3): each row is a body item."""
    assert el.rows
    if _INDEX_HEAD.match(fold(el.rows[0][0]).strip()):
        return True
    data = [row[0].strip() for row in el.rows[1:] if row[0].strip()]
    return bool(data) and sum(c.rstrip(".").isdigit() for c in data) * 2 > len(data)


def is_approval_table(el: DocElement) -> bool:
    """Prepared/Reviewed/Approved columns (or rows) with name/signature/date labels.

    The role words alone are not enough: a body table can have "Biên soạn | Soát xét | Phê
    duyệt" columns per document type. A sign-off grid also labels its rows (or columns) with
    "Họ tên" / "Chữ ký" / "Name" / "Signature"; a short grid without labels counts only when
    its rows are not numbered items.
    """
    if el.kind != "table" or not el.rows:
        return False
    head = fold(" ".join(c for row in el.rows[:2] for c in row))
    if not any(sum(term in head for term in terms) >= 2 for terms in _APPROVAL_TERMS):
        return False
    edge = [row[0] for row in el.rows[1:]] + list(el.rows[0][1:])
    if any(len(c) <= _MAX_LABEL_CELL and _SIGN_OFF_LABEL.search(fold(c)) for c in edge):
        return True
    return len(el.rows) <= _MAX_UNLABELLED_APPROVAL_ROWS and not _has_index_column(el)


def is_revision_table(el: DocElement) -> bool:
    if el.kind != "table" or not el.rows or is_approval_table(el):
        return False
    first, rest = fold(el.rows[0][0]), fold(" ".join(el.rows[0][1:]))
    return bool(_REVISION_HEAD.search(first) and _REVISION_COLUMN.search(rest))


def _is_motto_table(el: DocElement) -> bool:
    """The issuing body / national motto / number / place-and-date grid of a Vietnamese decree."""
    if not el.rows or len(el.rows) > _MAX_FRAME_TABLE_ROWS:
        return False
    cells = [c for row in el.rows for c in row if c.strip()]
    if any(len(c) > _MAX_FRAME_CHARS for c in cells):
        return False
    return any(p.search(fold(c)) for c in cells for p in _MOTTO)


def _mark(el: DocElement, role: str = "boilerplate") -> None:
    el.role = role  # type: ignore[assignment]


def mark_frame_blocks(doc: StructuredDocument) -> dict[int, str]:
    """Mark motto, number, recipients, signature and approval/revision tables as boilerplate.

    Returns ``{element index: kind}`` for the blocks this step marked.
    """
    kinds: dict[int, str] = {}
    body = [i for i, el in enumerate(doc.elements) if _in_body(el)]
    first_heading = next((i for i in body if doc.elements[i].kind == "heading"), None)

    def mark(index: int, kind: str) -> None:
        # The first heading is kept as the document title, unless its wording says it is frame:
        # the national motto (Docling often returns the motto block as the first heading of a
        # decree) or the title of a revision/approval table placed before the body.
        if index == first_heading and kind != "national_motto" and not kind.endswith("_title"):
            return
        _mark(doc.elements[index])
        kinds[index] = kind

    for index in body[:_LEADING_ELEMENTS]:
        el = doc.elements[index]
        if el.page not in (None, 1):
            continue
        if el.kind == "table":
            if _is_motto_table(el):
                mark(index, "national_motto")
            continue
        text = fold(el.text)
        if any(p.search(text) for p in _MOTTO) and len(el.text) <= _MAX_FRAME_CHARS:
            mark(index, "national_motto")
        elif _DOC_NUMBER.match(text) and len(el.text) <= _MAX_FRAME_CHARS \
                and "\n" not in el.text:
            mark(index, "document_number")
        elif _DOC_META_LINE.match(text) and len(el.text) <= _MAX_META_LINE:
            mark(index, "document_meta")

    body = [i for i in body if i not in kinds]
    _mark_recipients(doc, body, mark)
    body = [i for i in body if i not in kinds]
    _mark_signature(doc, body, mark)

    for index, el in enumerate(doc.elements):
        if not _in_body(el):
            continue
        kind = "approval_table" if is_approval_table(el) else \
            "revision_table" if is_revision_table(el) else None
        if kind is None:
            continue
        mark(index, kind)
        prev = index - 1
        while prev >= 0 and not _in_body(doc.elements[prev]) and prev not in kinds:
            prev -= 1  # skip elements that are already frame
        if prev >= 0 and doc.elements[prev].kind == "heading" \
                and _REVISION_TITLE.match(fold(doc.elements[prev].text)):
            mark(prev, f"{kind}_title")
    return kinds


def _mark_recipients(doc: StructuredDocument, body: list[int], mark) -> None:
    tail = body[-_TRAILING_ELEMENTS * 4:]
    for position, index in enumerate(tail):
        el = doc.elements[index]
        # "Nơi nhận:" is bold, so the extractor often returns it as a heading.
        if el.kind not in ("paragraph", "list_item", "heading") or len(el.text) > 80:
            continue
        match = _RECIPIENTS.match(fold(el.text))
        # A heading needs the colon: "Distribution" alone can be a body section title.
        if not match:
            continue
        if el.kind == "heading" and not match.group(0).rstrip().endswith((":", "：")):
            continue
        mark(index, "recipients")
        for follower in tail[position + 1:position + 1 + _MAX_RECIPIENT_ITEMS]:
            nxt = doc.elements[follower]
            dashed = nxt.kind == "paragraph" and nxt.text.lstrip().startswith(("-", "•", "–"))
            if len(nxt.text) > 100 or not (nxt.kind == "list_item" or dashed):
                break
            mark(follower, "recipients")
        return


def _mark_signature(doc: StructuredDocument, body: list[int], mark) -> None:
    tail = body[-_TRAILING_ELEMENTS:]
    for position, index in enumerate(tail):
        el = doc.elements[index]
        if el.kind not in ("paragraph", "heading") or len(el.text) > _MAX_SIGNATURE_LINE:
            continue
        text = fold(el.text)
        # A bold "KT. BỘ TRƯỞNG" line can come back as a heading; the signature-word rule stays
        # paragraph-only so a heading "Signature" in the body is kept.
        if not (_SIGNATURE_START.match(text)
                or (el.kind == "paragraph" and _SIGNATURE_WORD.match(text))):
            continue
        mark(index, "signature")
        for follower in tail[position + 1:]:
            nxt = doc.elements[follower]
            if nxt.kind != "paragraph" or len(nxt.text) > 60:
                break
            mark(follower, "signature")
        return


def collect_boilerplate(doc: StructuredDocument, kinds: dict[int, str]) -> list[BoilerplateBlock]:
    """Every element that is not body content, as ``{kind, page, text}`` in reading order."""
    blocks: list[BoilerplateBlock] = []
    for index, el in enumerate(doc.elements):
        if el.role in ("content", "figure_text") or el.kind == "page_break":
            continue
        text = element_text(el).strip()
        if not text:
            continue
        kind = kinds.get(index) or el.role
        blocks.append(BoilerplateBlock(kind=kind, page=el.page, text=text))
    return blocks
