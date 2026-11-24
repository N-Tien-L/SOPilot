"""CommonMark + GFM parser into ``StructuredDocument`` (V2-20).

Frontmatter is stored, Hugo shortcodes are removed, embedded HTML is kept as text.
"""
from __future__ import annotations

import re

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token

from sopilot_ai.docproc.errors import ExtractionError, FailureCode
from sopilot_ai.docproc.model import DocElement, StructuredDocument

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_SHORTCODE = re.compile(r"\{\{[<%].*?[>%]\}\}", re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ExtractionError(FailureCode.INVALID_ENCODING) from None


def _split_frontmatter(text: str) -> tuple[dict | None, str]:
    m = _FRONTMATTER.match(text)
    if not m:
        return None, text
    try:
        parsed = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None, text
    if not isinstance(parsed, dict):
        return None, text
    return parsed, text[m.end():]


def _inline_text(token: Token) -> str:
    parts: list[str] = []
    for child in token.children or []:
        if child.type == "html_inline":
            parts.append(_HTML_COMMENT.sub("", child.content))  # an HTML comment is not content
        elif child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif child.type == "image":
            parts.append(child.content)
    return "".join(parts)


_QUOTE_AFTER_BULLET = re.compile(r"\s*(?:[-*+]|\d{1,9}[.)])\s+>( ?)")


class _Builder:
    def __init__(self, lines: list[str] | None = None) -> None:
        self.elements: list[DocElement] = []
        self._lines = lines or []

    def _quote_marker(self, token: Token) -> str:
        """The ``>`` that opened a blockquote inside a list item, with the source's spacing."""
        start = token.map[0] if token.map else None
        if start is not None and start < len(self._lines):
            if m := _QUOTE_AFTER_BULLET.match(self._lines[start]):
                return ">" + m.group(1)
        return "> "

    def walk(self, tokens: list[Token], list_depth: int = 0) -> None:
        i = 0
        # Stack of (ordered, next_number) for the lists we are inside.
        counters: list[list[int | bool]] = []
        while i < len(tokens):
            t = tokens[i]
            if t.type == "heading_open":
                text = _inline_text(tokens[i + 1])
                self.elements.append(DocElement(kind="heading", level=int(t.tag[1]), text=text))
                i += 3
            elif t.type == "paragraph_open":
                self.elements.append(DocElement(kind="paragraph", text=_inline_text(tokens[i + 1])))
                i += 3
            elif t.type in ("bullet_list_open", "ordered_list_open"):
                ordered = t.type == "ordered_list_open"
                start = int(t.attrGet("start") or 1) if ordered else 0
                counters.append([ordered, start])
                i += 1
            elif t.type in ("bullet_list_close", "ordered_list_close"):
                counters.pop()
                i += 1
            elif t.type == "list_item_open":
                ordered, n = counters[-1]
                number = f"{n}." if ordered else None
                if ordered:
                    counters[-1][1] = int(n) + 1
                # First paragraph of the item becomes the list_item; the rest are walked on.
                j = i + 1
                text = ""
                if j < len(tokens) and tokens[j].type == "paragraph_open":
                    text = _inline_text(tokens[j + 1])
                    i = j + 3
                elif (j + 3 < len(tokens) and tokens[j].type == "blockquote_open"
                      and tokens[j + 1].type == "paragraph_open"):
                    # "- >$5,000 needs approval": the author means "greater than", and the
                    # item must not become an empty bullet followed by an orphan paragraph.
                    text = self._quote_marker(tokens[j]) + _inline_text(tokens[j + 2])
                    i = j + 4
                else:
                    i = j
                self.elements.append(DocElement(kind="list_item", text=text, number=number,
                                                level=len(counters)))
            elif t.type == "list_item_close":
                i += 1
            elif t.type == "table_open":
                i = self._table(tokens, i)
            elif t.type in ("fence", "code_block"):
                self.elements.append(DocElement(kind="code", text=t.content))
                i += 1
            elif t.type == "html_block":
                content = _HTML_COMMENT.sub("", t.content)
                if content.strip():
                    self.elements.append(DocElement(kind="paragraph", text=content))
                i += 1
            else:
                i += 1  # blockquote_open/close, hr: children are walked as normal blocks

    def _table(self, tokens: list[Token], i: int) -> int:
        rows: list[list[str]] = []
        row: list[str] = []
        while tokens[i].type != "table_close":
            t = tokens[i]
            if t.type == "tr_open":
                row = []
            elif t.type == "inline":
                row.append(_inline_text(t))
            elif t.type == "tr_close":
                rows.append(row)
            i += 1
        if rows:
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            self.elements.append(DocElement(kind="table", rows=rows))
        return i + 1


def extract_markdown(data: bytes) -> StructuredDocument:
    text = _decode(data)
    frontmatter, body = _split_frontmatter(text)
    body = _SHORTCODE.sub("", body)
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    # markdown-it numbers lines after normalising only CR/CRLF, so split the same way.
    builder = _Builder(body.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    builder.walk(md.parse(body))
    return StructuredDocument(file_type="MD", elements=builder.elements, page_count=None,
                              frontmatter=frontmatter)
