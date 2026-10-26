"""Document family detection (§5.4)."""
from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from sopilot_ai.docproc.chunk.headings import Node, is_article, resolve_outline
from sopilot_ai.docproc.chunk.procedure_table import is_procedure_table
from sopilot_ai.docproc.clean.boilerplate import fold
from sopilot_ai.docproc.model import DocElement

_ISO_SECTION_WORDS = ("muc dich", "pham vi", "noi dung", "purpose", "scope", "procedure",
                      "quy trinh", "trach nhiem", "responsibilit")
_MIN_ARTICLES = 3
_MIN_ISO_SECTIONS = 2


class DocFamily(StrEnum):
    ISO_PROCEDURE = "ISO_PROCEDURE"
    LEGAL_ARTICLES = "LEGAL_ARTICLES"
    MARKDOWN = "MARKDOWN"
    PROSE = "PROSE"


def family_of(nodes: Sequence[Node]) -> DocFamily:
    headings = [n for n in nodes if n.level is not None]
    if sum(1 for n in headings if is_article(n.title)) >= _MIN_ARTICLES:
        return DocFamily.LEGAL_ARTICLES
    iso_hits = {w for n in headings for w in _ISO_SECTION_WORDS if w in fold(n.title)}
    if len(iso_hits) >= _MIN_ISO_SECTIONS or any(is_procedure_table(n.el) for n in nodes):
        return DocFamily.ISO_PROCEDURE
    return DocFamily.MARKDOWN if headings else DocFamily.PROSE


def detect_family(elements: Sequence[DocElement]) -> DocFamily:
    """Family of a rendered document (``elements`` carry offsets, so only content is seen)."""
    return family_of(resolve_outline(elements))
