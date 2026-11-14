"""Rule-based part of metadata suggestions (V2-25, TECH-V2-ai-service §5.7). Pure: text in, out.

Rules run first and need no model: the title is the first heading of the extracted Markdown, or the
file title when there is none. The LLM only ever proposes description, category and tags.
"""
from __future__ import annotations

import re

TITLE_MAX = 200
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def headings(markdown: str, limit: int = 40) -> list[str]:
    """Heading lines in order (``## 1. Mục đích``), at most ``limit``."""
    out: list[str] = []
    for line in markdown.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            out.append(f"{m.group(1)} {m.group(2)}")
            if len(out) >= limit:
                break
    return out


def title_candidate(markdown: str, file_title: str) -> str:
    """First heading if there is one, else the file title. Never empty, never over 200 chars."""
    for line in markdown.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            return m.group(2).strip()[:TITLE_MAX]
    return file_title.strip()[:TITLE_MAX] or "Untitled"


def representative_paragraphs(markdown: str, n: int = 3, min_chars: int = 40) -> list[str]:
    """The first ``n`` prose paragraphs: not headings, not table rows, not short fragments."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", markdown):
        text = " ".join(line.strip() for line in block.splitlines()
                        if line.strip() and not line.lstrip().startswith(("#", "|")))
        if len(text) >= min_chars:
            out.append(text)
            if len(out) >= n:
                break
    return out
