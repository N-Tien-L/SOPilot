"""Post-generation checks (pure functions, TECH-V2-ai-service §7.1 steps 10-11).

- :func:`is_generator_not_found`: the model started with the fixed "not found" sentence (D2).
- :func:`check_numbers`: numbers, dates and amounts in the final answer that no source holds.
  It only flags (``NUMBER_NOT_IN_SOURCES``); it never edits or removes text that was streamed.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from sopilot_ai.qa import values
from sopilot_ai.qa.templates import not_found_openings

WARNING_CODE = "NUMBER_NOT_IN_SOURCES"

_LEAD = re.compile(r"^[\s\"'“”‘’*_>#\-–—.,:;!?()\[\]]+")
_SPACES = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _SPACES.sub(" ", unicodedata.normalize("NFC", text)).strip().casefold()


def is_generator_not_found(answer: str) -> bool:
    """True when the answer starts with the fixed opening sentence in either language.

    Deterministic string match: case-insensitive, whitespace-collapsed, leading punctuation and
    markdown marks ignored, the sentence's final period optional. Language does not matter: a
    Vietnamese question may still be answered in English.
    """
    head = _squash(_LEAD.sub("", answer))
    for opening in not_found_openings():
        if head.startswith(_squash(opening).rstrip(".")):
            return True
    return False


@dataclass(frozen=True)
class NumberCheck:
    values: tuple[str, ...]  # as written in the answer, first occurrence order

    @property
    def warned(self) -> bool:
        return bool(self.values)

    def warnings(self) -> list[dict]:
        """``done.warnings`` entries."""
        return [{"code": WARNING_CODE, "values": list(self.values)}] if self.values else []

    def to_checks(self) -> list[str]:
        """``messages.checks.numberWarnings``."""
        return list(self.values)


def check_numbers(answer: str, source_texts: Iterable[str]) -> NumberCheck:
    """Flag values of ``answer`` that appear in none of ``source_texts``.

    ``source_texts`` must hold everything the model was shown that can legitimately supply a
    value: the rendered sources including their ``code``/``rev``/``effective`` attributes, the
    system prompt's "today" line, and the question (working and original text): a situational
    answer repeats the user's own figures ("đơn 80 triệu"), which no source holds.
    """
    held = values.Values()
    for text in source_texts:
        v = values.extract(text)
        held.dates += v.dates
        held.amounts += v.amounts
        held.numbers += v.numbers
        held.amount_bases += v.amount_bases
    plain = held.number_keys() | held.amount_keys()  # a plain "50.000.000" backs "50 triệu"
    source_dates = held.date_keys()
    source_month_days = {k[5:] if len(k) == 10 else k for k in source_dates}

    got = values.extract(answer)
    missing: list[str] = []

    def add(text: str) -> None:
        if text not in missing:
            missing.append(text)

    for f in got.dates:
        known = f.key in source_dates if len(f.key) == 10 else f.key in source_month_days
        if not known:
            add(f.text)
    for f in got.amounts:
        if f.key not in plain:
            add(f.text)
    for f in got.numbers:
        if f.key not in plain and f.key not in held.base_keys():
            add(f.text)
    return NumberCheck(tuple(missing))
