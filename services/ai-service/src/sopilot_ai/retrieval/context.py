"""Context assembly: search with small chunks, read with whole sections (TECH-V2-ai-service §6.4a).

Pure functions over data the caller already fetched, so ``eval/`` imports them without a database.
The caller reads the section groups with one query that goes through the access filter (§6.1);
nothing here touches storage.

Steps for the hit chunks in rank order:

1. group = chunks of the same version and ``section_path``, by ``ordinal``;
2. group ≤ ``section_max_tokens`` -> take all of it; larger -> the hit, its two neighbours and,
   for a ``PROCEDURE_STEP`` / ``TABLE`` hit, the section's lead ``SECTION`` / ``PROSE`` chunk;
3. windows of one version that overlap or touch (adjacent ordinals) merge into one source whose
   rank is the best rank of its hits;
4. sources join by rank until ``max_tokens``; a source that does not fit shrinks to its hit chunks;
   if that still does not fit, stop. The top-ranked source is always kept.

``expand = False`` keeps the old behaviour: one source per hit chunk, no merging.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID

LEAD_TYPES = ("SECTION", "PROSE")
STEP_TYPES = ("PROCEDURE_STEP", "TABLE")

GroupKey = tuple[UUID, tuple[str, ...]]  # (version_id, section_path)


@dataclass(frozen=True)
class ChunkInfo:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    ordinal: int
    chunk_type: str
    section_path: tuple[str, ...]
    page_start: int | None
    char_start: int
    char_end: int
    content: str
    token_count: int


@dataclass(frozen=True)
class ContextConfig:
    expand: bool = True
    section_max_tokens: int = 1200
    max_tokens: int = 3000


@dataclass(frozen=True)
class Source:
    """One ``<source n="…">`` of the prompt."""

    n: int
    rank: int  # best (lowest) rank among its hit chunks, 1-based
    document_id: UUID
    version_id: UUID
    chunks: tuple[ChunkInfo, ...]  # by ordinal
    hit_chunk_ids: tuple[UUID, ...]  # in rank order
    reduced: bool = False  # shrunk to the hit chunks to fit the token cap

    @property
    def tokens(self) -> int:
        return sum(c.token_count for c in self.chunks)

    @property
    def section_path(self) -> tuple[str, ...]:
        return self.chunks[0].section_path

    @property
    def page(self) -> int | None:
        pages = [c.page_start for c in self.chunks if c.page_start is not None]
        return min(pages) if pages else None

    @property
    def text(self) -> str:
        """Chunk contents by ordinal, each run of one section under its own path line.

        Windows of neighbouring sections can merge into one source (§6.4a step 3), so the header
        is repeated when the section changes instead of labelling everything with the first one.
        """
        parts: list[str] = []
        current: tuple[str, ...] | None = None
        for c in self.chunks:
            if c.section_path != current:
                current = c.section_path
                if current:
                    parts.append(" > ".join(current))
            parts.append(c.content)
        return "\n\n".join(parts)

    @property
    def hit_chunks(self) -> tuple[ChunkInfo, ...]:
        by_id = {c.chunk_id: c for c in self.chunks}
        return tuple(by_id[i] for i in self.hit_chunk_ids)

    @property
    def best_hit(self) -> ChunkInfo:
        return self.hit_chunks[0]

    @property
    def hit_page(self) -> int | None:
        """First page of the hit chunks: where the highlighted span is, not the lead paragraph's."""
        pages = [c.page_start for c in self.hit_chunks if c.page_start is not None]
        return min(pages) if pages else None

    @property
    def hit_span(self) -> tuple[int, int]:
        """Character range covering the hit chunks (what the citation viewer highlights)."""
        hits = self.hit_chunks
        return min(c.char_start for c in hits), max(c.char_end for c in hits)

    @property
    def hit_snippet(self) -> str:
        return "\n\n".join(c.content for c in sorted(self.hit_chunks, key=lambda c: c.ordinal))


def group_key(chunk: ChunkInfo) -> GroupKey:
    return chunk.version_id, chunk.section_path


def group_keys(hits: Sequence[ChunkInfo]) -> list[GroupKey]:
    """Distinct (version, section) groups the caller must fetch, in first-seen order."""
    return list(dict.fromkeys(group_key(h) for h in hits))


def _window(hit: ChunkInfo, group: Sequence[ChunkInfo], section_max_tokens: int) -> list[ChunkInfo]:
    ordered = sorted({c.ordinal: c for c in [*group, hit]}.values(), key=lambda c: c.ordinal)
    if sum(c.token_count for c in ordered) <= section_max_tokens:
        return ordered
    pos = next(i for i, c in enumerate(ordered) if c.ordinal == hit.ordinal)
    chosen = ordered[max(0, pos - 1):pos + 2]
    if hit.chunk_type in STEP_TYPES:
        lead = next((c for c in ordered if c.chunk_type in LEAD_TYPES), None)
        if lead is not None and lead.ordinal not in {c.ordinal for c in chosen}:
            chosen = [lead, *chosen]
    return chosen


@dataclass
class _Window:
    version_id: UUID
    document_id: UUID
    chunks: dict[int, ChunkInfo]
    hits: list[tuple[int, ChunkInfo]] = field(default_factory=list)  # (rank, chunk)

    def touches(self, other: _Window) -> bool:
        if self.version_id != other.version_id:
            return False
        mine, theirs = set(self.chunks), set(other.chunks)
        return bool(mine & theirs) or any(o + 1 in theirs or o - 1 in theirs for o in mine)

    def absorb(self, other: _Window) -> None:
        self.chunks.update(other.chunks)
        self.hits += other.hits


def _source(w: _Window, *, reduced: bool = False) -> tuple[int, tuple[ChunkInfo, ...],
                                                            tuple[UUID, ...], bool]:
    hits = sorted(w.hits, key=lambda item: item[0])
    keep_ids = {c.chunk_id for _, c in hits}
    chunks = tuple(sorted(w.chunks.values(), key=lambda c: c.ordinal))
    if reduced:
        chunks = tuple(c for c in chunks if c.chunk_id in keep_ids)
    return hits[0][0], chunks, tuple(dict.fromkeys(c.chunk_id for _, c in hits)), reduced


def build_sources(hits: Sequence[ChunkInfo],
                  groups: Mapping[GroupKey, Sequence[ChunkInfo]],
                  cfg: ContextConfig | None = None) -> list[Source]:
    """Sources for the prompt from hit chunks (rank order) and their fetched section groups.

    A hit whose group is missing from ``groups`` is treated as a one-chunk group (fail closed:
    nothing beyond the hit is shown without having been fetched through the access filter).
    """
    cfg = cfg or ContextConfig()
    windows: list[_Window] = []
    for rank, hit in enumerate(hits, start=1):
        if cfg.expand:
            chunks = _window(hit, groups.get(group_key(hit), ()), cfg.section_max_tokens)
        else:
            chunks = [hit]
        windows.append(_Window(hit.version_id, hit.document_id,
                               {c.ordinal: c for c in chunks}, [(rank, hit)]))

    merged: list[_Window] = []
    if cfg.expand:
        for w in windows:
            touching = [m for m in merged if m.touches(w)]
            if not touching:
                merged.append(w)
                continue
            first = touching[0]
            first.absorb(w)
            for extra in touching[1:]:  # the new window bridged two earlier ones
                first.absorb(extra)
                merged.remove(extra)
    else:
        merged = windows

    merged.sort(key=lambda w: min(r for r, _ in w.hits))

    sources: list[Source] = []
    used = 0
    for w in merged:
        rank, chunks, hit_ids, reduced = _source(w)
        cost = sum(c.token_count for c in chunks)
        if sources and used + cost > cfg.max_tokens:
            rank, chunks, hit_ids, reduced = _source(w, reduced=True)
            cost = sum(c.token_count for c in chunks)
            if used + cost > cfg.max_tokens:
                break
        sources.append(Source(len(sources) + 1, rank, w.document_id, w.version_id, chunks,
                              hit_ids, reduced))
        used += cost
    return sources


def context_sources_json(sources: Sequence[Source]) -> list[dict]:
    """``messages.context_sources`` (TECH §3.4)."""
    return [{"n": s.n, "documentId": str(s.document_id), "versionId": str(s.version_id),
             "hitChunkIds": [str(i) for i in s.hit_chunk_ids],
             "chunkIds": [str(c.chunk_id) for c in s.chunks], "tokens": s.tokens}
            for s in sources]
