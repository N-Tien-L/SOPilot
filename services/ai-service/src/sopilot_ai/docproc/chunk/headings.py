"""Heading resolution for chunking (§5.4).

Order of evidence: real heading elements (Markdown ``#`` or a converter that reports levels), then
numbering patterns at the start of a short line (``1.``, ``5.1``, ``I.``, ``Điều n``,
``Chương n``, ``Article n``), and only if the document still has no heading, an all-caps line.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sopilot_ai.docproc.model import DocElement

MAX_HEADING_CHARS = 120  # a sentence ending in "." and longer than this is never a heading
_MAX_PROMOTED_CHARS = 100
_MAX_PROMOTED_WORDS = 12
_MAX_LONE_TITLE_WORDS = 8

_ARTICLE = re.compile(r"^(điều|article)\s+\d+[a-z]?(?:[.:]|\s*$)", re.IGNORECASE)
_CHAPTER = re.compile(r"^(chương|phần|chapter|part)\s+(\d+|[IVXLC]+)(?:[.:]|\s|$)", re.IGNORECASE)
_SECTION = re.compile(r"^(mục|section)\s+(\d+|[IVXLC]+)(?:[.:]|\s|$)", re.IGNORECASE)
_DOTTED = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(\S.*)$")
_ROMAN = re.compile(r"^([IVXLC]+)[.)]\s+(\S.*)$")

LEVEL_CHAPTER = 1
LEVEL_SECTION = 2
LEVEL_ARTICLE = 3


@dataclass
class Node:
    """An element with its heading level (``None`` for body content)."""

    el: DocElement
    level: int | None = None
    title: str = ""
    kind: str = ""  # "article" | "chapter" | "section" | "numbered" | "roman" | "heading" | "caps"


def is_article(title: str) -> bool:
    return bool(_ARTICLE.match(title.strip()))


def _full_text(el: DocElement) -> str:
    if el.kind == "list_item" and el.number:
        return f"{el.number} {el.text}".strip()
    return el.text.strip()


def _too_sentence_like(text: str) -> bool:
    return len(text) > MAX_HEADING_CHARS and text.rstrip().endswith(".")


def _classify(text: str, el: DocElement) -> tuple[int, str] | None:
    """Level and pattern kind if ``text`` opens like a heading, else ``None``."""
    if _ARTICLE.match(text):
        return LEVEL_ARTICLE, "article"
    if _CHAPTER.match(text):
        return LEVEL_CHAPTER, "chapter"
    if _SECTION.match(text):
        return LEVEL_SECTION, "section"
    if match := _ROMAN.match(text):
        if match.group(2).isupper():
            return 1, "roman"
        return None
    if match := _DOTTED.match(text):
        number, rest = match.groups()
        depth = number.count(".") + 1
        letters = [c for c in rest if c.isalpha()]
        words = len(rest.split())
        if not letters or words > _MAX_PROMOTED_WORDS or rest.rstrip().endswith((".", ";", ",")):
            return None
        if depth > 1 or rest.isupper():
            return depth, "numbered"
        if depth == 1 and el.kind == "paragraph" and len(text) <= 60:
            return 1, "numbered"
    return None


def resolve_outline(elements: Sequence[DocElement]) -> list[Node]:
    """One ``Node`` per rendered element, in order; headings carry a level and a title."""
    nodes: list[Node] = []
    for el in elements:
        if el.char_start is None:
            continue
        nodes.append(Node(el=el))

    real = [n for n in nodes if n.el.kind == "heading"]
    levels = {n.el.level or 1 for n in real}
    trust_levels = len(levels) > 1  # a hierarchy was reported: do not re-derive from numbers

    for position, node in enumerate(nodes):
        el = node.el
        text = _full_text(el)
        if el.kind == "heading":
            if _too_sentence_like(text):
                continue
            node.title, node.kind = text, "heading"
            node.level = el.level or 1
            if not trust_levels and (found := _classify(text, el)):
                node.level, node.kind = found
            elif trust_levels and (found := _classify(text, el)) and found[1] == "article":
                node.kind = "article"
        elif el.kind in ("paragraph", "list_item") and len(text) <= _MAX_PROMOTED_CHARS:
            found = _classify(text, el)
            if found is None and _is_lone_numbered_title(nodes, position, text):
                found = (1, "numbered")
            if found and "\n" not in text:
                node.title, node.level, node.kind = text, found[0], found[1]

    _lift_numeric_below_roman(nodes)
    if not any(n.level is not None for n in nodes):
        _promote_all_caps(nodes)
    return nodes


def _is_lone_numbered_title(nodes: list[Node], position: int, text: str) -> bool:
    """A short ``2. Procedure`` list item with no list item next to it.

    PDF converters often report a numbered section title as a list item. Steps of a real list sit
    next to each other, so a title-like item with no list-item neighbour is read as a heading.
    """
    el = nodes[position].el
    match = _DOTTED.match(text)
    if el.kind != "list_item" or not match or "." in match.group(1):
        return False
    rest = match.group(2)
    if len(rest.split()) > _MAX_LONE_TITLE_WORDS or rest.rstrip().endswith((".", ";", ",", ":")):
        return False
    neighbours = nodes[max(position - 1, 0):position] + nodes[position + 1:position + 2]
    return not any(n.el.kind == "list_item" for n in neighbours)


def _lift_numeric_below_roman(nodes: list[Node]) -> None:
    """``I.`` headings sit above ``1.`` headings: shift numbered levels down one."""
    if any(n.kind == "roman" for n in nodes):
        for node in nodes:
            if node.kind == "numbered" and node.level is not None:
                node.level += 1


def _promote_all_caps(nodes: list[Node]) -> None:
    for node in nodes:
        el = node.el
        text = el.text.strip()
        letters = [c for c in text if c.isalpha()]
        if el.kind != "paragraph" or len(letters) < 4 or len(text) > 80:
            continue
        if text.isupper() and not text.endswith(".") and "\n" not in text:
            node.title, node.level, node.kind = text, 1, "caps"
