"""BM25 tokenizer shared by ingest, query and the eval harness (TECH-V2-ai-service §6.3, D11).

The eval harness imports this module (§6.5), so ingest, the SQL BM25 and ``eval/`` share one
tokenizer. ``BM25`` is the in-memory reference the SQL of ``retrieval.search`` must match.
Changing the tokenizer requires ``admin reindex --all``.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from itertools import pairwise
from typing import Literal

import numpy as np

FOLD_PREFIX = "~"
K1 = 1.5
B = 0.75
TOKENIZER_VERSION = "nfc-lower-w+-uni+bi+fold~-v2"

_WORD = re.compile(r"\w+")


def fold(term: str) -> str:
    """Strip Vietnamese diacritics: NFD, drop combining marks, ``đ -> d``."""
    decomposed = unicodedata.normalize("NFD", term.replace("đ", "d").replace("Đ", "D"))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", stripped)


def base_terms(text: str) -> list[str]:
    r"""Lowercase NFC ``\w+`` unigrams plus ``a_b`` bigrams, diacritics preserved."""
    toks = _WORD.findall(unicodedata.normalize("NFC", text.lower()))
    return toks + [f"{a}_{b}" for a, b in pairwise(toks)]


def tokenize(text: str, role: Literal["document", "query"] = "document") -> list[str]:
    """Documents: base terms plus ``~folded`` (same tf) for terms that change when folded.

    Queries: base terms only if any term carries a diacritic; otherwise base terms plus
    ``~term`` for each, so "quy trinh" matches "quy trình" and English keeps its base match.
    """
    terms = base_terms(text)
    if role == "document":
        return terms + [FOLD_PREFIX + f for t in terms if (f := fold(t)) != t]
    if role == "query":
        if any(fold(t) != t for t in terms):
            return terms
        return terms + [FOLD_PREFIX + t for t in terms]
    raise ValueError("role must be document or query")


def lexical_len(text: str) -> int:
    """BM25 document length: base terms only, never the ``~`` terms."""
    return len(base_terms(text))


def term_frequencies(text: str) -> Counter[str]:
    """``rag.chunk_terms`` rows of one chunk's ``index_text``."""
    return Counter(tokenize(text, "document"))


class BM25:
    """In-memory BM25 over tokenized documents (eval harness; reference for the SQL, §6.3).

    ``idf = ln(1 + (N - df + 0.5) / (df + 0.5))``; ``lengths`` are :func:`lexical_len` values.
    """

    def __init__(self, docs: list[list[str]], k1: float = K1, b: float = B,
                 lengths: list[int] | None = None) -> None:
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array(lengths if lengths is not None else [len(d) for d in docs],
                            dtype=np.float32)
        self.avg = float(self.len.mean()) if len(docs) else 1.0
        self.avg = self.avg or 1.0
        df = Counter(t for d in self.tf for t in d)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        s = np.zeros(len(self.tf), dtype=np.float32)
        for t in set(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t)
                if f:
                    s[i] += idf * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return s
