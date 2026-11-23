from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from sopilot_ai.api.processing_report import (
    STRATEGY_RULES,
    chunk_response,
    report_response,
    signals_from,
    stats_of,
)
from sopilot_ai.docproc import DocElement, DocFamily, StructuredDocument, detect_family
from sopilot_ai.docproc.chunk.family import family_evidence
from sopilot_ai.docproc.chunk.headings import resolve_outline


def _h(text: str, level: int = 1) -> DocElement:
    return DocElement(kind="heading", text=text, level=level, char_start=0, char_end=len(text))


def _p(text: str) -> DocElement:
    return DocElement(kind="paragraph", text=text, char_start=0, char_end=len(text))


def _chunk(ordinal: int, kind: str, tokens: int) -> SimpleNamespace:
    return SimpleNamespace(ordinal=ordinal, chunk_type=kind, section_path=["1. Mục đích"],
                           page_start=1, page_end=1, char_start=ordinal * 10,
                           char_end=ordinal * 10 + 9, token_count=tokens)


def test_every_family_has_strategy_rules() -> None:
    assert set(STRATEGY_RULES) == {f.value for f in DocFamily}
    assert all(rules[-1] == "PREFIX" for rules in STRATEGY_RULES.values())


def test_evidence_counts_sop_section_words_without_diacritics() -> None:
    elements = [_h("1. Mục đích"), _p("x"), _h("2. Phạm vi"), _p("y")]
    ev = family_evidence(resolve_outline(elements))
    assert ev["headings"] == 2
    assert ev["sopSectionWords"] == ["muc dich", "pham vi"]
    assert ev["articleHeadings"] == 0
    assert detect_family(elements) is DocFamily.ISO_PROCEDURE


def test_evidence_counts_article_headings_for_a_legal_document() -> None:
    elements = [_h(f"Điều {i}. Quy định {i}", 3) for i in range(1, 4)]
    ev = family_evidence(resolve_outline(elements))
    assert ev["articleHeadings"] == 3
    assert detect_family(elements) is DocFamily.LEGAL_ARTICLES


def test_signals_are_recomputed_from_the_stored_structure() -> None:
    elements = [_h("Giới thiệu"), _p("nội dung")]
    stored = StructuredDocument(file_type="MD", elements=elements).model_dump(mode="json")
    signals = signals_from(stored)
    assert signals is not None and signals["headings"] == 1


def test_unreadable_structure_gives_no_signals_instead_of_an_error() -> None:
    assert signals_from({"file_type": "nonsense"}) is None


def test_stats_of_an_empty_list_are_zero() -> None:
    assert stats_of([]) == {"chunks": 0, "avgTokens": 0, "maxTokens": 0, "byType": {}}


def test_stats_count_types_and_tokens() -> None:
    rows = [_chunk(0, "SECTION", 100), _chunk(1, "PROCEDURE_STEP", 40), _chunk(2, "SECTION", 160)]
    assert stats_of(rows) == {"chunks": 3, "avgTokens": 100, "maxTokens": 160,
                              "byType": {"SECTION": 2, "PROCEDURE_STEP": 1}}


def test_the_report_lists_chunks_without_their_text() -> None:
    stored = StructuredDocument(file_type="MD", elements=[_h("Giới thiệu")]).model_dump(mode="json")
    row = SimpleNamespace(document_id=uuid4(), version_id=uuid4(), file_type="MD", language="vi",
                          doc_code="QT-07", page_count=None, doc_family="MARKDOWN",
                          structure=stored)
    out = report_response(row, [_chunk(0, "SECTION", 120)],
                          {"targetTokens": 384, "maxTokens": 512, "minTokens": 64})
    assert out["family"] == "MARKDOWN" and out["docCode"] == "QT-07"
    assert out["strategy"]["rules"] == STRATEGY_RULES["MARKDOWN"]
    assert out["strategy"]["config"]["maxTokens"] == 512
    assert "content" not in out["chunks"][0] and "markdown" not in out
    assert out["chunks"][0]["charEnd"] == 9


def test_one_chunk_detail_carries_the_embedded_text() -> None:
    row = SimpleNamespace(ordinal=3, chunk_type="PROCEDURE_STEP", section_path=["4. Quy trình"],
                          token_count=41, content="bước 3",
                          index_text="QT-07 › 4. Quy trình bước 3")
    assert chunk_response(row)["indexText"].endswith("bước 3")


def test_legal_articles_strategy_has_one_chunk_per_article() -> None:
    legal = STRATEGY_RULES["LEGAL_ARTICLES"]
    assert "ARTICLE_UNIT" in legal and "MERGE_SHORT" not in legal
    for family in ("ISO_PROCEDURE", "MARKDOWN"):
        assert "MERGE_SHORT" in STRATEGY_RULES[family]
        assert "ARTICLE_UNIT" not in STRATEGY_RULES[family]
