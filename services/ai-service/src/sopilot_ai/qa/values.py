"""Dates, amounts and numbers in free text (pure functions).

One extractor for two users: ``QueryFrame`` (what the question names) and ``checks`` (does the
answer state values that no source holds). Values are normalized so "50 triệu", "50.000.000" and
"50 000 000" compare equal, and "01/03/2026" equals "ngày 1 tháng 3 năm 2026".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from sopilot_ai.qa.resources import load_yaml

_NUM = r"\d+(?:[.,]\d+)*"


@dataclass(frozen=True)
class Found:
    key: str  # normalized: ISO date, "MM-DD" for a date without year, or a canonical decimal
    text: str  # as written


@dataclass
class Values:
    dates: list[Found] = field(default_factory=list)
    amounts: list[Found] = field(default_factory=list)  # a number with a unit ("50 triệu")
    numbers: list[Found] = field(default_factory=list)  # every other number
    amount_bases: list[Found] = field(default_factory=list)  # "50" of "50 triệu"

    def number_keys(self) -> set[str]:
        return {f.key for f in self.numbers}

    def amount_keys(self) -> set[str]:
        return {f.key for f in self.amounts}

    def base_keys(self) -> set[str]:
        return {f.key for f in self.amount_bases}

    def date_keys(self) -> set[str]:
        return {f.key for f in self.dates}


@lru_cache(maxsize=1)
def _units() -> tuple[dict[str, int], re.Pattern[str]]:
    raw = load_yaml("frame_rules.yaml")["amount_units"]
    units = {str(k).lower(): int(v) for k, v in raw.items()}
    alt = "|".join(re.escape(u) for u in sorted(units, key=len, reverse=True))
    return units, re.compile(rf"(?P<num>{_NUM})\s?(?P<unit>{alt})(?![\w])", re.IGNORECASE)


_DATE_DMY = re.compile(r"(?<![\d.,/-])(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})(?![\d])")
_DATE_ISO = re.compile(r"(?<![\d/.-])(\d{4})-(\d{2})-(\d{2})(?![\d])")
_DATE_VI = re.compile(
    r"(?:ngày\s+)?(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s*,?\s*(?:năm\s+)?(\d{4}))?", re.IGNORECASE)
_NUMBER = re.compile(rf"(?<![\w.,]){_NUM}(?![\w])")
_CITATION = re.compile(r"\[\d+(?:\s*[,;]\s*\d+)*\]")
_LIST_MARKER = re.compile(r"(?m)^\s*\d{1,2}[.)]\s")


def to_decimal(text: str) -> Decimal | None:
    """Parse ``1.000.000``, ``1,000``, ``2,5``, ``2.5`` (a lone separator before exactly three
    digits is a thousands separator, as in Vietnamese)."""
    s = text.strip()
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        s = re.sub(r"[.,]", "", s)
    elif re.fullmatch(r"\d+[.,]\d+", s):
        s = s.replace(",", ".")
    elif re.fullmatch(r"\d+(?:[.,]\d+){2,}", s):
        head, _, tail = s.replace(",", ".").rpartition(".")
        s = head.replace(".", "") + "." + tail
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _canon(d: Decimal) -> str:
    text = format(d.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _mask(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def extract(text: str) -> Values:
    out = Values()
    work = _CITATION.sub(lambda m: " " * len(m.group(0)), text)
    work = _LIST_MARKER.sub(lambda m: " " * len(m.group(0)), work)

    def dates(pattern: re.Pattern[str], order: str) -> None:
        nonlocal work
        for m in list(pattern.finditer(work)):
            g = m.groups()
            if order == "dmy":
                d, mo, y = int(g[0]), int(g[1]), g[2]
            elif order == "ymd":
                y, mo, d = g[0], int(g[1]), int(g[2])
            else:
                d, mo, y = int(g[0]), int(g[1]), g[2]
            if y:
                key = _iso(int(y), mo, d)
            else:
                key = f"{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else None
            if key:
                out.dates.append(Found(key, m.group(0).strip()))
                work = _mask(work, m.start(), m.end())

    dates(_DATE_ISO, "ymd")
    dates(_DATE_DMY, "dmy")
    dates(_DATE_VI, "vi")

    units, unit_re = _units()
    for m in list(unit_re.finditer(work)):
        n = to_decimal(m.group("num"))
        if n is None:
            continue
        value = n * units[m.group("unit").lower()]
        out.amounts.append(Found(_canon(value), m.group(0).strip()))
        out.amount_bases.append(Found(_canon(n), m.group("num")))
        work = _mask(work, m.start(), m.end())

    for m in _NUMBER.finditer(work):
        n = to_decimal(m.group(0))
        if n is not None:
            out.numbers.append(Found(_canon(n), m.group(0)))
    return out
