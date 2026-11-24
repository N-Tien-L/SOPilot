"""Context assembly (TECH-V2-ai-service §6.4a): groups, windows, merging, token cap."""
from __future__ import annotations

from uuid import UUID, uuid4

from sopilot_ai.retrieval.context import (
    ChunkInfo,
    ContextConfig,
    build_sources,
    context_sources_json,
    group_keys,
)

DOC, VER = uuid4(), uuid4()
SEC = ("5. Mua hàng", "5.1 Lập đề nghị")


def chunk(ordinal: int, *, kind="PROSE", tokens=100, section=SEC, ver: UUID = VER,
          doc: UUID = DOC, page: int | None = 1) -> ChunkInfo:
    return ChunkInfo(uuid4(), doc, ver, ordinal, kind, section, page, ordinal * 1000,
                     ordinal * 1000 + 900, f"c{ordinal}", tokens)


def groups(*chunks: ChunkInfo) -> dict:
    out: dict = {}
    for c in chunks:
        out.setdefault((c.version_id, c.section_path), []).append(c)
    return out


def ordinals(source) -> list[int]:
    return [c.ordinal for c in source.chunks]


def test_a_small_section_is_taken_whole():
    lead, s1, s2, s3 = (chunk(1), chunk(2, kind="PROCEDURE_STEP"), chunk(3, kind="PROCEDURE_STEP"),
                        chunk(4, kind="PROCEDURE_STEP"))
    out = build_sources([s2], groups(lead, s1, s2, s3), ContextConfig(section_max_tokens=1200))
    assert len(out) == 1
    assert ordinals(out[0]) == [1, 2, 3, 4]
    assert out[0].hit_chunk_ids == (s2.chunk_id,)


def test_a_large_section_takes_the_hit_its_neighbours_and_the_lead_paragraph():
    cs = [chunk(1, tokens=300)] + [chunk(i, kind="PROCEDURE_STEP", tokens=300) for i in range(2, 9)]
    out = build_sources([cs[5]], groups(*cs), ContextConfig(section_max_tokens=1200))
    assert ordinals(out[0]) == [1, 5, 6, 7]  # lead, hit ordinal 6 with neighbours 5 and 7


def test_the_lead_paragraph_is_only_added_for_steps_and_tables():
    cs = [chunk(1, tokens=300)] + [chunk(i, tokens=300) for i in range(2, 9)]
    out = build_sources([cs[5]], groups(*cs), ContextConfig(section_max_tokens=1200))
    assert ordinals(out[0]) == [5, 6, 7]


def test_a_hit_at_the_edge_has_one_neighbour():
    cs = [chunk(i, tokens=400) for i in range(1, 6)]
    out = build_sources([cs[0]], groups(*cs), ContextConfig(section_max_tokens=1000))
    assert ordinals(out[0]) == [1, 2]


def test_windows_that_touch_merge_and_keep_the_best_rank():
    cs = [chunk(i, tokens=400) for i in range(1, 9)]
    # hits: ordinal 3 (rank 1) and ordinal 5 (rank 2): windows [2,3,4] and [4,5,6] overlap.
    out = build_sources([cs[2], cs[4]], groups(*cs), ContextConfig(section_max_tokens=1000,
                                                                     max_tokens=10_000))
    assert len(out) == 1
    assert ordinals(out[0]) == [2, 3, 4, 5, 6]
    assert out[0].rank == 1
    assert out[0].hit_chunk_ids == (cs[2].chunk_id, cs[4].chunk_id)


def test_windows_with_adjacent_ordinals_merge():
    cs = [chunk(i, tokens=400) for i in range(1, 12)]
    out = build_sources([cs[1], cs[5]], groups(*cs), ContextConfig(section_max_tokens=1000,
                                                                     max_tokens=10_000))
    # windows [1,2,3] and [5,6,7]: ordinal 4 separates them, so two sources
    assert [ordinals(s) for s in out] == [[1, 2, 3], [5, 6, 7]]
    out = build_sources([cs[1], cs[4]], groups(*cs), ContextConfig(section_max_tokens=1000,
                                                                     max_tokens=10_000))
    # windows [1,2,3] and [4,5,6] touch (3 and 4 are adjacent)
    assert [ordinals(s) for s in out] == [[1, 2, 3, 4, 5, 6]]


def test_chunks_of_other_versions_or_sections_are_never_merged():
    other_ver = uuid4()
    a = chunk(1)
    b = chunk(2, ver=other_ver)
    c = chunk(3, section=("6. Thanh toán",))
    out = build_sources([a, b, c], groups(a, b, c))
    assert len(out) == 3
    assert [s.version_id for s in out] == [VER, other_ver, VER]


def test_sources_are_numbered_by_rank():
    a, b = chunk(1, section=("A",)), chunk(1, section=("B",), doc=uuid4(), ver=uuid4())
    out = build_sources([b, a], groups(a, b))
    assert [(s.n, s.rank) for s in out] == [(1, 1), (2, 2)]
    assert out[0].document_id == b.document_id


def test_the_token_cap_shrinks_a_source_to_its_hits_then_stops():
    a = [chunk(i, tokens=400, section=("A",)) for i in range(1, 4)]  # 1200 tokens, whole
    b_ver = uuid4()
    b = [chunk(i, tokens=400, section=("B",), ver=b_ver) for i in range(1, 4)]
    c_ver = uuid4()
    c = [chunk(i, tokens=400, section=("C",), ver=c_ver) for i in range(1, 4)]
    cfg = ContextConfig(section_max_tokens=1200, max_tokens=1900)
    out = build_sources([a[1], b[1], c[1]], groups(*a, *b, *c), cfg)
    # A takes 1200; B (1200) does not fit but its hit alone (400) does; C's hit (400) no longer
    assert len(out) == 2
    assert ordinals(out[0]) == [1, 2, 3] and out[0].reduced is False
    assert ordinals(out[1]) == [2] and out[1].reduced is True
    assert out[1].hit_chunk_ids == (b[1].chunk_id,)


def test_the_top_source_is_kept_even_over_the_cap():
    a = [chunk(i, tokens=900, section=("A",)) for i in range(1, 4)]
    out = build_sources([a[1]], groups(*a), ContextConfig(section_max_tokens=5000, max_tokens=1000))
    assert len(out) == 1 and out[0].tokens == 2700


def test_expand_false_gives_one_source_per_hit_chunk_without_merging():
    cs = [chunk(i, tokens=100) for i in range(1, 5)]
    out = build_sources([cs[0], cs[1]], groups(*cs), ContextConfig(expand=False))
    assert [ordinals(s) for s in out] == [[1], [2]]
    assert [s.hit_chunk_ids for s in out] == [(cs[0].chunk_id,), (cs[1].chunk_id,)]


def test_a_group_that_was_not_fetched_gives_only_the_hit():
    # Fail closed: nothing but the hit is shown when the caller fetched no group for it.
    hit = chunk(3)
    out = build_sources([hit], {})
    assert [ordinals(s) for s in out] == [[3]]


def test_group_keys_lists_each_section_once_in_first_seen_order():
    a, b, c = chunk(1), chunk(2), chunk(1, section=("X",))
    assert group_keys([a, c, b]) == [(VER, SEC), (VER, ("X",))]


def test_a_source_spanning_two_sections_names_each_section_in_its_text():
    a = chunk(5, section=("5. Mua hàng", "5.1 Lập đề nghị"))
    b = chunk(6, section=("5. Mua hàng", "5.2 Duyệt"))
    out = build_sources([a, b], groups(a, b), ContextConfig(section_max_tokens=50))
    assert len(out) == 1 and ordinals(out[0]) == [5, 6]
    assert out[0].text == ("5. Mua hàng > 5.1 Lập đề nghị\n\nc5\n\n"
                           "5. Mua hàng > 5.2 Duyệt\n\nc6")


def test_citation_page_is_the_page_of_the_hit_not_of_the_lead_paragraph():
    lead, hit = chunk(1, page=1), chunk(2, kind="PROCEDURE_STEP", page=3)
    out = build_sources([hit], groups(lead, hit))[0]
    assert out.page == 1 and out.hit_page == 3


def test_render_citation_span_and_json():
    lead, hit = chunk(1, page=2), chunk(2, kind="PROCEDURE_STEP", page=3)
    out = build_sources([hit], groups(lead, hit))[0]
    assert out.text == "5. Mua hàng > 5.1 Lập đề nghị\n\nc1\n\nc2"
    assert out.page == 2
    assert out.hit_span == (2000, 2900)  # only the hit chunk, not the lead paragraph
    assert out.hit_snippet == "c2"
    j = context_sources_json([out])[0]
    assert j["n"] == 1 and j["hitChunkIds"] == [str(hit.chunk_id)]
    assert j["chunkIds"] == [str(lead.chunk_id), str(hit.chunk_id)]
    assert j["tokens"] == 200
