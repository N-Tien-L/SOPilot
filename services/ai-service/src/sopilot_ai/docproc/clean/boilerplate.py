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

_EDGE_ELEMENTS = 2  # elements per page edge considered as header/footer candidates
_MAX_FRAME_CHARS = 200  # a longer block is a paragraph, never a header/footer line
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


def _repeat_key(el: DocElement) -> str:
    return re.sub(r"\d+", "#", " ".join(el.text.lower().split()))


def mark_repeated_header_footer(doc: StructuredDocument, config: CleanConfig) -> None:
    """Lines present at the same page edge on >= ratio of the pages become header/footer.

    Skipped below ``header_footer_min_pages``: with one or two pages every edge line would reach
    the ratio and the title and last paragraph would be removed.
    """
    if doc.file_type != "PDF" or not doc.page_count:
        return
    if doc.page_count < config.header_footer_min_pages:
        return
    by_page: dict[int, list[int]] = defaultdict(list)
    for index, el in enumerate(doc.elements):
        if el.page is not None and _in_body(el) and el.kind in ("paragraph", "heading",
                                                                 "list_item"):
            by_page[el.page].append(index)
    first_heading = next((i for i, el in enumerate(doc.elements)
                          if el.kind == "heading" and _in_body(el)), None)
    seen: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for page, indexes in by_page.items():
        zones = [("header", indexes[:_EDGE_ELEMENTS]), ("footer", indexes[-_EDGE_ELEMENTS:])]
        taken: set[int] = set()
        for zone, picks in zones:
            for index in picks:
                el = doc.elements[index]
                if index in taken or not el.text.strip() or len(el.text) > _MAX_FRAME_CHARS:
                    continue
                taken.add(index)
                seen[(zone, _repeat_key(el))].append((page, index))
    needed = config.header_footer_ratio * doc.page_count
    for (zone, _), hits in seen.items():
        if len({page for page, _ in hits}) < needed:
            continue
        for _, index in hits:
            if index != first_heading:
                doc.elements[index].role = zone  # type: ignore[assignment]


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
_REVISION_HEAD = re.compile(r"sua doi|revision|change|history|ban hanh|\brev\b")
_REVISION_COLUMN = re.compile(r"ngay|date|noi dung|description|content|nguoi|by")
_REVISION_TITLE = re.compile(
    r"^(bang )?(theo doi )?(sua doi|revision history|change history|lich su sua doi)")


def is_approval_table(el: DocElement) -> bool:
    if el.kind != "table" or not el.rows:
        return False
    head = fold(" ".join(c for row in el.rows[:2] for c in row))
    return any(sum(term in head for term in terms) >= 2 for terms in _APPROVAL_TERMS)


def is_revision_table(el: DocElement) -> bool:
    if el.kind != "table" or not el.rows or is_approval_table(el):
        return False
    head = fold(" ".join(el.rows[0]))
    return bool(_REVISION_HEAD.search(head) and _REVISION_COLUMN.search(head))


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
        if index == first_heading:
            return
        _mark(doc.elements[index])
        kinds[index] = kind

    for index in body[:_LEADING_ELEMENTS]:
        el = doc.elements[index]
        if el.kind == "table" or el.page not in (None, 1):
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
        if prev >= 0 and doc.elements[prev].kind == "heading" and prev != first_heading \
                and _REVISION_TITLE.match(fold(doc.elements[prev].text)):
            mark(prev, f"{kind}_title")
    return kinds


def _mark_recipients(doc: StructuredDocument, body: list[int], mark) -> None:
    tail = body[-_TRAILING_ELEMENTS * 4:]
    for position, index in enumerate(tail):
        el = doc.elements[index]
        if el.kind not in ("paragraph", "list_item") or len(el.text) > 80:
            continue
        if not _RECIPIENTS.match(fold(el.text)):
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
        if el.kind != "paragraph" or len(el.text) > _MAX_SIGNATURE_LINE:
            continue
        text = fold(el.text)
        if not (_SIGNATURE_START.match(text) or _SIGNATURE_WORD.match(text)):
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
