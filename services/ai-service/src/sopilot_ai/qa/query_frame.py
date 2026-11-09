"""``QueryFrame``: everything the rules learn about a question, computed once.

Built by a pure function right after the PII step (TECH-V2-ai-service §7.1). The router, retrieval
and the prompt read the frame instead of detecting language, document codes or follow-up markers
again. The comparison signal is only recorded in ``messages.route``; it never changes the route.
"""
from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from sopilot_ai.qa import values
from sopilot_ai.qa.doc_code import find_doc_codes
from sopilot_ai.qa.resources import load_yaml
from sopilot_ai.qa.textnorm import Token, match_phrases, nfc, tokenize_words
from sopilot_ai.retrieval.lexical import fold

Lang = Literal["vi", "en"]

@lru_cache(maxsize=1)
def _rules() -> dict:
    frame = load_yaml("frame_rules.yaml")
    follow = load_yaml("followup_rules.yaml")
    return {
        "ratio": float(frame["language"]["vi_diacritic_ratio"]),
        "vi_unaccented": tuple(frame["language"]["vi_unaccented_markers"]),
        "comparison": tuple(frame["comparison"]["keywords"]),
        "min_doc_codes": int(frame["comparison"]["min_doc_codes"]),
        "followup": tuple(follow["markers"]["vi"]) + tuple(follow["markers"]["en"]),
        "followup_max_tokens": int(follow["max_tokens"]),
        "lexicon": tuple(load_yaml("lexicon.yaml")["words"]),
    }


def detect_lang(text: str, override: str | None = None) -> Lang:
    """``override`` ("vi"/"en" from the request) wins; else the share of letters with a
    Vietnamese diacritic, with unaccented Vietnamese markers as a fallback; default English."""
    if override in ("vi", "en"):
        return override  # type: ignore[return-value]
    letters = [c for c in nfc(text) if c.isalpha()]
    if letters:
        marked = sum(1 for c in letters if fold(c) != c)
        if marked / len(letters) >= _rules()["ratio"]:
            return "vi"
    padded = f" {fold(nfc(text).lower())} "
    if any(f" {m} " in padded for m in _rules()["vi_unaccented"]):
        return "vi"
    return "en"


@dataclass(frozen=True)
class QueryFrame:
    text: str  # NFC, after PII masking; the tokens' spans index into it
    lang: Lang
    tokens: tuple[Token, ...]
    doc_codes: frozenset[str]
    dates: tuple[str, ...]
    amounts: tuple[str, ...]
    followup_marker: bool  # a demonstrative / "what about" marker is present
    short: bool  # fewer than `followup_max_tokens` tokens
    comparison: bool
    meaningful: frozenset[int]  # indexes of tokens that count as meaningful

    @property
    def followup_signal(self) -> bool:
        return self.followup_marker or self.short

    def meaningful_count(self, removed: Collection[int] = ()) -> int:
        """Meaningful tokens left once the tokens at ``removed`` (greetings, profanity) are cut."""
        return len(self.meaningful - set(removed))

    def signals(self) -> dict[str, bool]:
        """What goes into ``messages.route.signals``. Recorded only, never branched on."""
        return {"comparison": self.comparison, "followup": self.followup_signal}


def build_query_frame(text: str, *, lang: str | None = None,
                      known_terms: Collection[str] = (),
                      followup_max_tokens: int | None = None) -> QueryFrame:
    """Build the frame of the PII-masked question.

    ``known_terms``: lowercase NFC tokens present in the asker's own documents (the caller reads
    them from ``rag.chunk_terms`` through the access filter) so a word of their corpus counts as
    meaningful without being in the lexicon.
    """
    rules = _rules()
    text = nfc(text)
    tokens = tokenize_words(text)
    max_short = rules["followup_max_tokens"] if followup_max_tokens is None else followup_max_tokens

    meaningful = {t.index for t in tokens if t.raw in known_terms and not t.raw.isdigit()}
    for _, idx in match_phrases(tokens, rules["lexicon"], use_folded=False):
        meaningful.update(idx)
    # Unaccented spelling only for phrases: a folded single word collides ("đúng"/"dung",
    # "mưa"/"mua", "nghĩ"/"nghi"); a lone unaccented word is covered by the corpus terms.
    folded_phrases = [fold(w) for w in rules["lexicon"] if " " in w]
    for _, idx in match_phrases(tokens, folded_phrases, use_folded=True):
        meaningful.update(idx)

    codes = find_doc_codes(text)
    found = values.extract(text)
    keywords = [w.lower() for w in rules["comparison"]]
    comparison = (len(codes) >= rules["min_doc_codes"]
                  or bool(match_phrases(tokens, keywords))
                  or bool(match_phrases(tokens, [fold(k) for k in keywords], use_folded=True)))
    markers = bool(match_phrases(tokens, rules["followup"]))

    return QueryFrame(
        text=text,
        lang=detect_lang(text, lang),
        tokens=tokens,
        doc_codes=frozenset(codes),
        dates=tuple(f.key for f in found.dates),
        amounts=tuple(f.key for f in found.amounts),
        followup_marker=markers,
        short=len(tokens) < max_short,
        comparison=comparison,
        meaningful=frozenset(meaningful),
    )
