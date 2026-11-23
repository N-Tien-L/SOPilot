"""Pure chunk-quality metrics for the pilot corpus (V2-47). No Docling, corpus or model.

Inputs are plain dicts: ``[c.model_dump() for c in chunks]`` and the rendered Markdown. Definitions:

* ``under_min``: chunks with ``token_count < min_tokens`` and ``kind != "PROCEDURE_STEP"``.
* ``no_letters``: chunks whose ``content`` has no ``str.isalpha()`` character (any kind).
* ``step_chunks``: chunks with ``kind == "PROCEDURE_STEP"``.
* ``uncovered_body``: rendered elements with ``char_start`` not None that are body content (the
  outline node has ``level is None``) and whose ``[char_start, char_end)`` overlaps no chunk's
  ``[char_start, char_end)``. Heading elements are excluded because their text is in
  ``section_path``. The count and up to 5 snippets (first 60 chars, whitespace collapsed) are
  reported.
* ``markdown_sha256``: sha256 hex of the rendered Markdown (UTF-8).
"""
from __future__ import annotations

import hashlib

SNIPPET_CHARS = 60
MAX_EXAMPLES = 5


def under_min(chunks: list[dict], min_tokens: int) -> int:
    return sum(1 for c in chunks
               if c["token_count"] < min_tokens and c["kind"] != "PROCEDURE_STEP")


def no_letters(chunks: list[dict]) -> int:
    return sum(1 for c in chunks if not any(ch.isalpha() for ch in c["content"]))


def step_chunks(chunks: list[dict]) -> int:
    return sum(1 for c in chunks if c["kind"] == "PROCEDURE_STEP")


def uncovered_body(spans: list[tuple[int, int, bool]], chunks: list[dict],
                   markdown: str) -> tuple[int, list[str]]:
    """``spans`` is ``(char_start, char_end, is_body)`` per rendered element with offsets."""
    count, examples = 0, []
    for start, end, is_body in spans:
        if not is_body:
            continue
        if any(c["char_start"] < end and c["char_end"] > start for c in chunks):
            continue
        count += 1
        if len(examples) < MAX_EXAMPLES:
            examples.append(" ".join(markdown[start:end].split())[:SNIPPET_CHARS])
    return count, examples


def markdown_sha256(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()
