"""Rule-based language detection for a document version (TECH-V2-ai-service §5.1 step 6).

Returns ``vi``, ``en`` or ``None`` (unknown). Only these two languages are in scope (PRD-V2), so
a letter-class heuristic is enough and adds no dependency.
"""
from __future__ import annotations

import re
import unicodedata

_WORD = re.compile(r"[^\W\d_]+")
# Letters that exist in Vietnamese but not in plain ASCII English.
_VI_BASE = set("đăâêôơư")
_EN_HINTS = {"the", "and", "of", "to", "is", "for", "with", "shall", "must", "be", "are", "this"}


def _is_vietnamese_word(word: str) -> bool:
    if any(c in _VI_BASE for c in word):
        return True
    return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", word))


def detect_language(text: str, sample_chars: int = 20000) -> str | None:
    words = _WORD.findall(text[:sample_chars].lower())
    if len(words) < 5:
        return None
    vi = sum(1 for w in words if _is_vietnamese_word(w))
    if vi / len(words) >= 0.15:
        return "vi"
    ascii_words = sum(1 for w in words if w.isascii())
    if ascii_words / len(words) >= 0.9 and sum(1 for w in words if w in _EN_HINTS) >= 2:
        return "en"
    return None
