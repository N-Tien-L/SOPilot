"""Word tokens with positions, shared by the guard, the router and the query frame.

Everything below works on one NFC string, so a token's span can be cut out of the original text
("bóc rồi xét", TECH-V2-ai-service §7.1) without touching the rest of it.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from sopilot_ai.retrieval.lexical import fold

_WORD = re.compile(r"\w+")
_LEET = str.maketrans("013457", "oieast")


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


@dataclass(frozen=True)
class Token:
    index: int
    raw: str  # lowercase NFC, diacritics kept
    folded: str  # diacritics stripped and, for letter+digit tokens, leetspeak undone
    start: int
    end: int


def tokenize_words(text: str) -> tuple[Token, ...]:
    """``\\w+`` tokens of the NFC text with spans in that NFC text."""
    out = []
    for i, m in enumerate(_WORD.finditer(text)):
        raw = m.group(0).lower()
        folded = fold(raw)
        if any(c.isdigit() for c in folded) and any(c.isalpha() for c in folded):
            folded = folded.translate(_LEET)
        out.append(Token(i, raw, folded, m.start(), m.end()))
    return tuple(out)


def match_phrases(tokens: Sequence[Token], phrases: Collection[str], *,
                  use_folded: bool = False) -> list[tuple[str, tuple[int, ...]]]:
    """Whole-word matches of phrases (``"khốn nạn"``) against consecutive tokens.

    Returns ``(phrase, token indexes)``. A phrase never matches inside a longer word, which is
    why "ngu" does not fire on "nguồn". Longer phrases win over their own prefixes.
    """
    key = (lambda t: t.folded) if use_folded else (lambda t: t.raw)
    split = sorted(((p, tuple(p.lower().split())) for p in phrases),
                   key=lambda item: -len(item[1]))
    used: set[int] = set()
    found: list[tuple[str, tuple[int, ...]]] = []
    for i in range(len(tokens)):
        if i in used:
            continue
        for phrase, words in split:
            n = len(words)
            if i + n <= len(tokens) and all(key(tokens[i + k]) == words[k] for k in range(n)):
                idx = tuple(range(i, i + n))
                if used.isdisjoint(idx):
                    used.update(idx)
                    found.append((phrase, idx))
                    break
    return found


def remove_tokens(text: str, tokens: Sequence[Token], indexes: Collection[int]) -> str:
    """``text`` without the spans of the given tokens, whitespace collapsed, edges trimmed."""
    drop = sorted((tokens[i].start, tokens[i].end) for i in set(indexes))
    pieces, pos = [], 0
    for start, end in drop:
        pieces.append(text[pos:start])
        pos = end
    pieces.append(text[pos:])
    cleaned = re.sub(r"\s+", " ", "".join(pieces))
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip(" \t\n,.;:!-—")
