"""PII masking by rules (TECH-V2-ai-service §7.1 step 2, owner D8).

Emails, Vietnamese phone numbers, and ID / account numbers **only** when a keyword precedes them
within 20 characters, so an amount such as ``500.000.000`` or a bare digit string is left alone.
The masked text is the working text for every later step; ``messages.content`` keeps the original.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Groups of 2-4 digits, so a date such as "05-03-2026 10" (one-digit groups) never reads as a
# phone number. The digit count is checked in the replacement.
_PHONE = re.compile(r"(?<![\w+])(?:\+84|0)(?:[ .\-]?\d{2,4}){2,4}(?!\d)")
_MONEY = re.compile(r"\d{1,3}(?:\.\d{3})+")  # "500.000.000": thousands grouping, an amount

_ID_KEYWORDS = r"cccd|cmnd|căn cước(?: công dân)?|can cuoc|hộ chiếu|ho chieu|passport"
_ACCOUNT_KEYWORDS = r"stk|số tài khoản|so tai khoan|account"
_NUMBER = r"\d(?:[ .\-]?\d){7,15}"
_KEYED = re.compile(
    rf"(?<!\w)(?P<kw>{_ID_KEYWORDS}|{_ACCOUNT_KEYWORDS})(?P<gap>[^\d\n]{{0,20}}?)(?P<num>{_NUMBER})(?!\d)",
    re.IGNORECASE)
_ID_KW = re.compile(rf"^(?:{_ID_KEYWORDS})$", re.IGNORECASE)

# CCCD/CMND 9 or 12 digits (current) and the 10-11 digit variants seen in practice: after a keyword,
# any 9-12 digit run is masked (owner D8, 2026-11-08). Leaking an ID costs more than over-masking.
_ID_LENGTHS = frozenset(range(9, 13))


@dataclass(frozen=True)
class PiiResult:
    text: str
    rule_ids: tuple[str, ...]  # unique, in order of first use: pii.email, pii.phone, ...


def mask_pii(text: str) -> PiiResult:
    rules: list[str] = []

    def note(rule: str) -> None:
        if rule not in rules:
            rules.append(rule)

    def keyed(m: re.Match[str]) -> str:
        if _MONEY.fullmatch(m.group("num")):
            return m.group(0)  # "account limit 500.000.000" is an amount, not an account number
        digits = re.sub(r"\D", "", m.group("num"))
        is_id = bool(_ID_KW.match(m.group("kw")))
        if is_id and len(digits) in _ID_LENGTHS:
            note("pii.id")
            tag = "[ID]"
        elif not is_id and 9 <= len(digits) <= 16:
            note("pii.account")
            tag = "[ACCOUNT]"
        else:
            return m.group(0)
        return f"{m.group('kw')}{m.group('gap')}{tag}"

    out = _KEYED.sub(keyed, text)
    out = _EMAIL.sub(lambda _m: (note("pii.email"), "[EMAIL]")[1], out)

    def phone(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        valid = len(digits) == 11 if m.group(0).startswith("+84") else len(digits) == 10
        if not valid:
            return m.group(0)
        note("pii.phone")
        return "[PHONE]"

    out = _PHONE.sub(phone, out)
    return PiiResult(out, tuple(rules))
