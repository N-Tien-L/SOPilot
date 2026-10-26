"""SOP metadata from the frame: document code, issue label, dates, approver (§5.3)."""
from __future__ import annotations

import re
from datetime import date

from sopilot_ai.docproc.clean.boilerplate import element_text, fold, is_approval_table
from sopilot_ai.docproc.clean.model import ExtractedMeta
from sopilot_ai.docproc.model import DocElement, StructuredDocument

_LEADING_ELEMENTS = 12

_CODE_LABEL = re.compile(
    r"(?:mã số|mã hiệu|số hiệu|mã tài liệu|ký hiệu|document\s*(?:no|number|code|id)|doc\.?\s*no"
    r"|code)\s*[:：.]?\s*([A-Za-z0-9][A-Za-z0-9._/\-]{1,39})", re.IGNORECASE)
_NUMBER_LABEL = re.compile(r"\bSố\s*[:：]\s*(\d+(?:/[\w\-ĐđÀ-ỹ]+)+)")
_CODE_SHAPE = re.compile(r"\b[A-Z]{2,5}(?:-[A-Z0-9]{1,6}){1,3}\b")
_REVISION = re.compile(
    r"(?:lần\s+(?:ban\s+hành|sửa\s+đổi|soát\s+xét)|revision|rev\.?|issue(?:\s+no\.?)?"
    r"|version|phiên\s+bản|ver\.?)\s*[:：]?\s*(\d{1,3}(?:\.\d{1,2})?[A-Za-z]?)\b", re.IGNORECASE)
_EFFECTIVE = re.compile(
    r"(?:ngày\s+hiệu\s+lực|hiệu\s+lực\s+từ|hiệu\s+lực|effective(?:\s+date)?)\s*[:：]?\s*(.{6,40})",
    re.IGNORECASE)
_ISSUED = re.compile(
    r"(?:ngày\s+ban\s+hành|issue\s+date|date\s+of\s+issue|issued(?:\s+on)?)\s*[:：]?\s*(.{6,40})",
    re.IGNORECASE)
_APPROVER = re.compile(
    r"(?:phê\s+duyệt|approved\s+by|approver|người\s+duyệt)\s*[:：]\s*([^|;\n]{3,60})",
    re.IGNORECASE)

_DMY = re.compile(r"(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})")
_YMD = re.compile(r"(\d{4})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})")
_VI_DATE = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)
_ROLE_WORDS = ("ho ten", "name", "ten", "nguoi")


def parse_date(text: str) -> str | None:
    """First date in ``text`` as ISO ``YYYY-MM-DD``; day-first for ``a/b/yyyy``."""
    for pattern, order in ((_VI_DATE, "dmy"), (_DMY, "dmy"), (_YMD, "ymd")):
        match = pattern.search(text)
        if not match:
            continue
        a, b, c = (int(g) for g in match.groups())
        day, month, year = (a, b, c) if order == "dmy" else (c, b, a)
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    return None


def _approver_from_table(table: DocElement) -> str | None:
    """Name under the Approved/Phê duyệt column (first non-empty row below the header)."""
    assert table.rows
    column = next((c for c, cell in enumerate(table.rows[0])
                   if re.search(r"phe duyet|approved|nguoi phe", fold(cell))), None)
    if column is None:
        return None
    labelled = [row for row in table.rows[1:]
                if any(w in fold(row[0]) for w in _ROLE_WORDS)]
    for row in labelled or table.rows[1:]:
        value = row[column].strip()
        if value and not re.fullmatch(r"[\d/.\-\s]+", value):
            return value
    return None


def _frame_texts(doc: StructuredDocument) -> list[str]:
    """Frame blocks first, then the leading content of the first page."""
    texts = [element_text(el) for el in doc.elements
             if el.role not in ("content", "figure_text") and el.kind != "table"]
    leading = [el for el in doc.elements
               if el.role in ("content", "figure_text") and el.page in (None, 1)]
    texts += [el.text for el in leading[:_LEADING_ELEMENTS] if el.kind != "table"]
    return texts  # tables are skipped: a revision history lists old revisions and dates


def extract_metadata(doc: StructuredDocument) -> ExtractedMeta:
    """Search the frame (before it is dropped) and the head of the document."""
    meta = ExtractedMeta()
    front = {k.lower(): v for k, v in (doc.frontmatter or {}).items() if isinstance(k, str)}
    for field, keys in (("doc_code", ("doc_code", "doccode", "code")),
                        ("revision_label", ("revision", "version", "revision_label")),
                        ("approved_by", ("approved_by", "approver"))):
        value = next((front[k] for k in keys if front.get(k) not in (None, "")), None)
        if value is not None:
            setattr(meta, field, str(value).strip())
    for field, keys in (("effective_date", ("effective_date", "effective")),
                        ("issue_date", ("issue_date", "issued"))):
        value = next((front[k] for k in keys if front.get(k) not in (None, "")), None)
        if value is not None:
            setattr(meta, field, parse_date(str(value)))

    for el in doc.elements:
        if el.kind == "table" and el.rows and is_approval_table(el) and not meta.approved_by:
            meta.approved_by = _approver_from_table(el)

    texts = _frame_texts(doc)
    for raw in texts:
        text = " ".join(raw.split())
        if not meta.doc_code:
            match = _CODE_LABEL.search(text) or _NUMBER_LABEL.search(text)
            if match and any(ch.isdigit() for ch in match.group(1)):
                meta.doc_code = match.group(1).rstrip(".,;:")
        if not meta.revision_label and (match := _REVISION.search(text)):
            meta.revision_label = match.group(1)
        if not meta.effective_date and (match := _EFFECTIVE.search(text)):
            meta.effective_date = parse_date(match.group(1))
        if not meta.issue_date and (match := _ISSUED.search(text)):
            meta.issue_date = parse_date(match.group(1))
        if not meta.approved_by and (match := _APPROVER.search(text)):
            meta.approved_by = match.group(1).strip()
    if not meta.doc_code:
        for text in texts:
            match = next((m for m in _CODE_SHAPE.finditer(text)
                          if any(ch.isdigit() for ch in m.group(0))), None)
            if match:
                meta.doc_code = match.group(0)
                break
    return meta
