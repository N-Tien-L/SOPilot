"""Structure-aware chunker (V2-22, TECH-V2-ai-service §5.4).

Works on a ``RenderedDocument``: every content element already carries its ``[char_start,
char_end)`` on the canonical Markdown, so a chunk is either an exact substring of ``markdown``
or, for procedure rows and split table parts, a text built from a row whose offsets are the
row's span. Token counts come from the ``Tokenizer`` passed in; nothing here imports providers.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from sopilot_ai.docproc.chunk.family import DocFamily, family_of
from sopilot_ai.docproc.chunk.headings import Node, resolve_outline
from sopilot_ai.docproc.chunk.procedure_table import is_procedure_table, step_rows
from sopilot_ai.docproc.errors import ExtractionError, FailureCode
from sopilot_ai.docproc.model import DocElement, RenderedDocument
from sopilot_ai.docproc.tokens import Tokenizer

ChunkKind = Literal["TEXT", "TABLE", "PROCEDURE_STEP"]

_SENTENCE_BREAK = re.compile(r"(?<=[.!?…;])\s+|\n+")
_SEPARATOR = " › "


@dataclass(frozen=True)
class ChunkConfig:
    """``chunking`` section of ``models.yaml`` (target 384, max 512, min 64)."""

    target_tokens: int = 384
    max_tokens: int = 512
    min_tokens: int = 64


class Chunk(BaseModel):
    kind: ChunkKind = "TEXT"
    content: str
    index_text: str  # what is embedded and indexed: title path + content
    section_path: list[str]  # ancestors of the section, ending with its own heading
    page_start: int | None = None
    page_end: int | None = None
    char_start: int
    char_end: int
    token_count: int  # tokens of ``index_text``


@dataclass
class _Block:
    el: DocElement
    start: int
    end: int


@dataclass
class _Section:
    path: list[str]
    level: int
    heading: _Block | None
    blocks: list[_Block] = field(default_factory=list)


@dataclass
class _Piece:
    start: int
    end: int
    page: int | None
    page_end: int | None


def index_prefix(title: str, doc_code: str | None, path: list[str]) -> str:
    """``"{title} [{doc_code}] › a › b"``; the code part only when a code was extracted."""
    head = title.strip()
    if doc_code:
        head = f"{head} [{doc_code}]" if head else f"[{doc_code}]"
    return _SEPARATOR.join(([head] if head else []) + path)


def _safe_cut(text: str, index: int) -> int:
    """Move ``index`` left so a combining mark or joiner is not separated from its base."""
    while index > 0 and index < len(text) and (
            unicodedata.combining(text[index]) or text[index] in "‍️"):
        index -= 1
    return index


class Chunker:
    def __init__(self, tokenizer: Tokenizer, config: ChunkConfig | None = None) -> None:
        self.tokenizer = tokenizer
        self.config = config or ChunkConfig()
        if not 0 < self.config.target_tokens <= self.config.max_tokens:
            raise ValueError("target_tokens must be in 1..max_tokens")

    def chunk(self, rendered: RenderedDocument, *, title: str = "",
              doc_code: str | None = None, family: DocFamily | None = None) -> list[Chunk]:
        nodes = resolve_outline(rendered.elements)
        family = family or family_of(nodes)
        sections = self._sections(nodes)
        if family is not DocFamily.LEGAL_ARTICLES:
            sections = self._merge_small(sections, rendered.markdown)
        chunks: list[Chunk] = []
        for section in sections:
            prefix = self._bounded_prefix(title, doc_code, section.path)
            chunks += self._section_chunks(section, prefix, rendered.markdown)
        if not chunks:
            raise ExtractionError(FailureCode.EMPTY_CONTENT)
        return chunks

    # -- sections ---------------------------------------------------------------------------

    @staticmethod
    def _sections(nodes: list[Node]) -> list[_Section]:
        sections = [_Section(path=[], level=0, heading=None)]
        stack: list[tuple[int, str]] = []
        for node in nodes:
            block = _Block(node.el, node.el.char_start or 0, node.el.char_end or 0)
            if node.level is None:
                sections[-1].blocks.append(block)
                continue
            while stack and stack[-1][0] >= node.level:
                stack.pop()
            stack.append((node.level, node.title))
            sections.append(_Section(path=[t for _, t in stack], level=node.level,
                                     heading=block))
        return [s for s in sections if s.blocks or s.heading]

    def _tokens(self, text: str) -> int:
        return self.tokenizer.count(text)

    def _body_tokens(self, section: _Section, markdown: str) -> int:
        return sum(self._tokens(markdown[b.start:b.end]) for b in section.blocks)

    def _merge_small(self, sections: list[_Section], markdown: str) -> list[_Section]:
        """Fold a section under ``min_tokens`` into the next sibling with the same parent."""
        merged: list[_Section] = []
        i = 0
        while i < len(sections):
            current = sections[i]
            total = self._body_tokens(current, markdown)
            while (current.blocks and total < self.config.min_tokens
                   and i + 1 < len(sections)
                   and self._is_sibling(current, sections[i + 1])
                   and not self._has_rows(sections[i + 1])
                   and not self._has_rows(current)):
                nxt = sections[i + 1]
                added = self._body_tokens(nxt, markdown)
                if total + added > self.config.target_tokens:
                    break
                if nxt.heading:
                    current.blocks.append(nxt.heading)
                current.blocks += nxt.blocks
                total += added
                i += 1
            merged.append(current)
            i += 1
        return merged

    @staticmethod
    def _is_sibling(a: _Section, b: _Section) -> bool:
        return b.heading is not None and a.level == b.level and a.path[:-1] == b.path[:-1]

    @staticmethod
    def _has_rows(section: _Section) -> bool:
        return any(is_procedure_table(b.el) for b in section.blocks)

    def _bounded_prefix(self, title: str, doc_code: str | None, path: list[str]) -> str:
        """The title path, shortened when it alone would take over half of ``max_tokens``.

        Ancestors go first (the section's own heading stays), then trailing words.
        """
        half = self.config.max_tokens // 2
        for keep in range(len(path), 0, -1):
            prefix = index_prefix(title, doc_code, path[len(path) - keep:])
            if self._tokens(prefix) <= half:
                return prefix
        words = index_prefix(title, doc_code, path[-1:]).split(" ")
        while len(words) > 1 and self._tokens(" ".join(words)) > half:
            words.pop()
        return " ".join(words)

    # -- chunk construction -----------------------------------------------------------------

    def _section_chunks(self, section: _Section, prefix: str, markdown: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        run: list[_Block] = []

        def flush() -> None:
            if run:
                chunks.extend(self._pack(run, prefix, section.path, markdown))
                run.clear()

        for block in section.blocks:
            if is_procedure_table(block.el):
                flush()
                chunks.extend(self._procedure_chunks(block, prefix, section.path))
            else:
                run.append(block)
        flush()
        return chunks

    def _index_text(self, prefix: str, content: str) -> str:
        return f"{prefix}\n{content}" if prefix else content

    def _fits(self, prefix: str, content: str, limit: int | None = None) -> bool:
        return self._tokens(self._index_text(prefix, content)) <= (limit or self.config.max_tokens)

    def _make(self, kind: ChunkKind, content: str, prefix: str, path: list[str],
              start: int, end: int, page: int | None, page_end: int | None) -> Chunk:
        index_text = self._index_text(prefix, content)
        return Chunk(kind=kind, content=content, index_text=index_text, section_path=list(path),
                     page_start=page, page_end=page_end if page is not None else None,
                     char_start=start, char_end=end, token_count=self._tokens(index_text))

    # Text, lists and small tables are packed up to ``target_tokens``; oversized ones are split.

    def _pack(self, blocks: list[_Block], prefix: str, path: list[str],
              markdown: str) -> list[Chunk]:
        pieces: list[_Piece] = []
        chunks: list[Chunk] = []
        for block in blocks:
            if block.el.kind == "table" and not self._fits(
                    prefix, markdown[block.start:block.end]):
                chunks += self._pack_pieces(pieces, prefix, path, markdown)
                pieces = []
                chunks += self._table_parts(block, prefix, path, markdown)
            else:
                pieces += self._block_pieces(block, prefix, markdown)
        chunks += self._pack_pieces(pieces, prefix, path, markdown)
        return chunks

    def _block_pieces(self, block: _Block, prefix: str, markdown: str) -> list[_Piece]:
        el = block.el
        whole = _Piece(block.start, block.end, el.page, el.page_end)
        text = markdown[block.start:block.end]
        if self._fits(prefix, text):
            return [whole]
        return [_Piece(block.start + s, block.start + e, el.page, el.page_end)
                for s, e in self._split_text(text, prefix)]

    def _pack_pieces(self, pieces: list[_Piece], prefix: str, path: list[str],
                     markdown: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        group: list[_Piece] = []

        def flush() -> None:
            if not group:
                return
            start, end = group[0].start, group[-1].end
            pages = [p.page for p in group if p.page is not None]
            ends = [p.page_end or p.page for p in group if p.page is not None]
            chunks.append(self._make("TEXT", markdown[start:end], prefix, path, start, end,
                                     min(pages) if pages else None,
                                     max(ends) if ends else None))
            group.clear()

        for piece in pieces:
            if group and not self._fits(prefix, markdown[group[0].start:piece.end],
                                        self.config.target_tokens):
                flush()
            group.append(piece)
        flush()
        return chunks

    # Splitting text that does not fit: sentences first, then words, never inside a character.

    def _split_text(self, text: str, prefix: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        position = 0
        for match in _SENTENCE_BREAK.finditer(text):
            if match.start() > position:
                spans.append((position, match.start()))
            position = match.end()
        if position < len(text):
            spans.append((position, len(text)))
        out: list[tuple[int, int]] = []
        for start, end in spans:
            if self._fits(prefix, text[start:end]):
                out.append((start, end))
            else:
                out += [(start + a, start + b) for a, b in self._split_words(text[start:end],
                                                                               prefix)]
        return out

    def _split_words(self, text: str, prefix: str) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        start = 0
        while start < len(text):
            if self._fits(prefix, text[start:]):
                out.append((start, len(text)))
                break
            end = self._largest_fit(text, start, prefix)
            out.append((start, end))
            start = end
            while start < len(text) and text[start].isspace():
                start += 1
        return out

    def _largest_fit(self, text: str, start: int, prefix: str) -> int:
        """Largest end > start such that ``text[start:end]`` fits; word boundary if one fits."""
        boundaries = [i for i in range(start + 1, len(text)) if text[i].isspace()]
        for candidates in (boundaries, list(range(start + 1, len(text)))):
            lo, hi, best = 0, len(candidates) - 1, None
            while lo <= hi:
                mid = (lo + hi) // 2
                if self._fits(prefix, text[start:candidates[mid]]):
                    best, lo = candidates[mid], mid + 1
                else:
                    hi = mid - 1
            if best is not None:
                cut = _safe_cut(text, best)
                if cut > start:
                    return cut
        return min(start + 1, len(text))  # a single character that cannot fit: still progress

    # Tables that exceed the budget are cut by row with the column header repeated.

    def _table_parts(self, block: _Block, prefix: str, path: list[str],
                     markdown: str) -> list[Chunk]:
        el = block.el
        assert el.rows and el.row_spans
        header_end = el.row_spans[0][1]
        separator = "| " + " | ".join(["---"] * len(el.rows[0])) + " |"
        header = markdown[el.row_spans[0][0]:header_end] + "\n" + separator
        chunks: list[Chunk] = []
        first = 1  # first data row of the part being built
        last: int | None = None  # last data row that still fits in the part
        for row in range(1, len(el.rows)):
            if last is not None and self._fits(
                    prefix, self._table_text(markdown, el, header, first, row),
                    self.config.target_tokens):
                last = row
                continue
            if last is not None:
                chunks.append(self._table_chunk(markdown, el, header, first, last, prefix, path))
                first = row
            if self._fits(prefix, self._table_text(markdown, el, header, row, row)):
                last = row
            else:  # one row alone is over budget: split its own text, header not repeated
                chunks += self._oversized_row(markdown, el, row, prefix, path)
                first, last = row + 1, None
        if last is not None:
            chunks.append(self._table_chunk(markdown, el, header, first, last, prefix, path))
        if not chunks:  # header-only table that is itself too long
            text = markdown[block.start:block.end]
            chunks = [self._make("TABLE", text[a:b], prefix, path, block.start + a,
                                 block.start + b, el.page, el.page_end)
                      for a, b in self._split_words(text, prefix)]
        return chunks

    @staticmethod
    def _table_text(markdown: str, el: DocElement, header: str, first: int, last: int) -> str:
        assert el.row_spans
        if first == 1:
            return markdown[el.char_start:el.row_spans[last][1]]
        rows = "\n".join(markdown[a:b] for a, b in el.row_spans[first:last + 1])
        return f"{header}\n{rows}"

    def _table_chunk(self, markdown: str, el: DocElement, header: str, first: int, last: int,
                     prefix: str, path: list[str]) -> Chunk:
        assert el.row_spans
        pages = el.row_pages[first:last + 1] if el.row_pages else None
        return self._make("TABLE", self._table_text(markdown, el, header, first, last), prefix,
                          path, el.row_spans[first][0], el.row_spans[last][1],
                          min(pages) if pages else el.page,
                          max(pages) if pages else el.page_end)

    def _oversized_row(self, markdown: str, el: DocElement, row: int, prefix: str,
                       path: list[str]) -> list[Chunk]:
        assert el.row_spans
        start, end = el.row_spans[row]
        text = markdown[start:end]
        page = el.row_pages[row] if el.row_pages else el.page
        return [self._make("TABLE", text[a:b], prefix, path, start, end, page, page)
                for a, b in self._split_words(text, prefix)]

    # Procedure rows: one chunk per row, offsets and page from the source row.

    def _procedure_chunks(self, block: _Block, prefix: str, path: list[str]) -> list[Chunk]:
        el = block.el
        assert el.row_spans
        chunks: list[Chunk] = []
        for step in step_rows(el):
            start, end = el.row_spans[step.row]
            page = el.row_pages[step.row] if el.row_pages else el.page
            if self._fits(prefix, step.content):
                parts = [(0, len(step.content))]
            else:
                parts = self._split_text(step.content, prefix)
            chunks += [self._make("PROCEDURE_STEP", step.content[a:b], prefix, path, start, end,
                                  page, page) for a, b in parts]
        return chunks


def chunk_document(rendered: RenderedDocument, tokenizer: Tokenizer, *, title: str = "",
                   doc_code: str | None = None, config: ChunkConfig | None = None,
                   family: DocFamily | None = None) -> list[Chunk]:
    """Chunk a rendered, cleaned document. Raises ``EMPTY_CONTENT`` when nothing is left."""
    return Chunker(tokenizer, config).chunk(rendered, title=title, doc_code=doc_code,
                                            family=family)
