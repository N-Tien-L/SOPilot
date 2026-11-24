"""Document codes in a question (TECH-V2-ai-service §6.4, owner D2 2026-10-21).

A question such as "QT-MH-01 quy định gì về duyệt?" names a document; chunks of the version whose
``extracted_meta.docCode`` matches get ``retrieval.doc_code_boost``. Matching is on the
uppercased question; codes compare after uppercasing and removing whitespace.
"""
from __future__ import annotations

import re

# Starting pattern of §6.4, bounded so it does not fire inside a longer word.
_CODE = re.compile(r"(?<![\wĐ])[A-ZĐ]{1,6}(?:[-/][A-Z0-9]{1,8}){1,3}(?![\w])")


def normalize_code(code: str) -> str:
    return "".join(code.upper().split())


def find_doc_codes(question: str) -> set[str]:
    """Normalized substrings that match the code pattern (letters, then 1–3 ``-``/``/`` parts).

    A false positive costs nothing: the boost applies only when a candidate's ``docCode``
    equals one of these.
    """
    return {normalize_code(m.group(0)) for m in _CODE.finditer(question.upper())}
