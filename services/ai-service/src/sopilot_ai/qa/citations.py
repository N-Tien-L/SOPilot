"""Citation post-processing (pure functions, TECH-V2-ai-service §7.1 step 9, §6.4a).

``[n]`` in the answer must point at a ``<source n="…">`` that was in the prompt. A marker that
does not is removed from the text. Each valid ``n`` becomes one ``message_citations`` row built
from the hit chunks of source ``n``.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sopilot_ai.retrieval.context import Source

# "[1]", and the grouped forms models like to write: "[1, 2]", "[1;2]".
_MARKER = re.compile(r"([ \t]*)\[(\d+(?:\s*[,;]\s*\d+)*)\]")


@dataclass(frozen=True)
class Citation:
    n: int
    chunk_id: UUID  # best-ranked hit chunk of the source
    document_id: UUID
    version_id: UUID
    page_start: int | None
    char_start: int
    char_end: int
    snippet: str


def clean_markers(text: str, valid: set[int]) -> tuple[str, list[int]]:
    """Remove ``[n]`` that map to no source. Returns ``(text, used)``.

    ``used`` lists the valid numbers in order of first appearance. A grouped marker keeps its
    valid numbers as separate ``[n]``. Removing a marker also removes the space before it.
    """
    used: list[int] = []

    def fix(match: re.Match[str]) -> str:
        nums = [int(x) for x in re.split(r"\s*[,;]\s*", match.group(2))]
        keep = [n for n in dict.fromkeys(nums) if n in valid]
        for n in keep:
            if n not in used:
                used.append(n)
        return match.group(1) + "".join(f"[{n}]" for n in keep) if keep else ""

    return _MARKER.sub(fix, text), used


def build_citations(sources: Sequence[Source], used: Sequence[int]) -> list[Citation]:
    """One citation per used ``n``: the best hit chunk, the span covering its hit chunks, and the
    text of those chunks as the snippet (a copy, so it survives a later document replacement)."""
    by_n = {s.n: s for s in sources}
    out = []
    for n in used:
        s = by_n.get(n)
        if s is None:
            continue
        start, end = s.hit_span
        out.append(Citation(n, s.best_hit.chunk_id, s.document_id, s.version_id, s.hit_page,
                            start, end, s.hit_snippet))
    return out
