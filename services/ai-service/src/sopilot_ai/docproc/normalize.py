"""Text normalization applied before rendering (NFC, whitespace)."""
from __future__ import annotations

import re
import unicodedata

from sopilot_ai.docproc.model import StructuredDocument

_SPACES = re.compile(r"[ \t   ]+")
_LINE_BREAK_RUN = re.compile(r"\s*[\r\n  ]+\s*")
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def normalize_text(text: str) -> str:
    """NFC, drop zero-width characters, turn hard line breaks into single spaces, trim."""
    text = unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH)
    text = _LINE_BREAK_RUN.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def normalize_code(text: str) -> str:
    """Code keeps its line structure; only NFC and newline style change."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return text.strip("\n")


def normalize_document(doc: StructuredDocument) -> StructuredDocument:
    """Return a copy of ``doc`` with every text field normalized (step 2a)."""
    elements = []
    for el in doc.elements:
        update: dict = {}
        if el.kind == "code":
            update["text"] = normalize_code(el.text)
        else:
            update["text"] = normalize_text(el.text)
        if el.number is not None:
            update["number"] = normalize_text(el.number)
        if el.rows is not None:
            update["rows"] = [[normalize_text(c) for c in row] for row in el.rows]
        elements.append(el.model_copy(update=update))
    return doc.model_copy(update={"elements": elements})
