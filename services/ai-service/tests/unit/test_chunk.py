from __future__ import annotations

import sys
import types
import unicodedata

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sopilot_ai.docproc import (
    ChunkConfig,
    DocElement,
    DocFamily,
    ExtractionError,
    FailureCode,
    StructuredDocument,
    chunk_document,
    clean_document,
    detect_family,
    extract,
    render,
)
from sopilot_ai.docproc.chunk import index_prefix
from sopilot_ai.docproc.tokens import HFTokenizer


class Words:
    """Whitespace tokenizer: deterministic and independent of any model download."""

    def count(self, text: str) -> int:
        return len(text.split())


def _h(text: str, level: int = 1, page: int | None = None) -> DocElement:
    return DocElement(kind="heading", text=text, level=level, page=page)


def _p(text: str, page: int | None = None) -> DocElement:
    return DocElement(kind="paragraph", text=text, page=page)


def _chunks(elements, file_type="PDF", pages=1, title="Quy trình mua hàng", code=None,
            config=None, family=None):
    doc = StructuredDocument(file_type=file_type, elements=elements,
                             page_count=pages if file_type == "PDF" else None)
    rendered = render(doc)
    out = chunk_document(rendered, Words(), title=title, doc_code=code, config=config,
                         family=family)
    return rendered, out


def _check_invariants(rendered, chunks, config=None):
    config = config or ChunkConfig()
    for c in chunks:
        assert c.token_count == len(c.index_text.split()) <= config.max_tokens
        assert 0 <= c.char_start < c.char_end <= len(rendered.markdown)
        if c.kind == "TEXT":
            assert rendered.markdown[c.char_start:c.char_end] == c.content
        if c.page_start is not None:
            assert c.page_start <= c.page_end


# -- headings and section_path -------------------------------------------------------------


def test_section_path_is_the_ancestor_chain_not_the_siblings():
    _, chunks = _chunks([
        _h("5. Quy định", 1), _p("Nội dung mục năm."),
        _h("5.1 Chung", 2), _p("Nội dung mục năm một."),
        _h("5.2 Riêng", 2), _p("Nội dung mục năm hai."),
        _h("6. Hồ sơ", 1), _p("Nội dung mục sáu."),
    ], config=ChunkConfig(min_tokens=1))
    paths = {c.content: c.section_path for c in chunks}
    assert paths["Nội dung mục năm."] == ["5. Quy định"]
    assert paths["Nội dung mục năm một."] == ["5. Quy định", "5.1 Chung"]
    assert paths["Nội dung mục năm hai."] == ["5. Quy định", "5.2 Riêng"]
    assert paths["Nội dung mục sáu."] == ["6. Hồ sơ"]


def test_flat_pdf_headings_get_their_level_from_numbering():
    _, chunks = _chunks([
        _h("5. Quy định", 1), _h("5.1 Chung", 1), _p("Chi tiết."),
        _h("5.1.1 Con", 1), _p("Chi tiết con."),
    ], config=ChunkConfig(min_tokens=1))
    assert chunks[-1].section_path == ["5. Quy định", "5.1 Chung", "5.1.1 Con"]


def test_heading_text_is_kept_in_full_including_title_only_after_number():
    _, chunks = _chunks([_p("1. MỤC ĐÍCH"), _p("Quy định cách mua hàng.")])
    assert chunks[0].section_path == ["1. MỤC ĐÍCH"]
    assert chunks[0].index_text.startswith("Quy trình mua hàng › 1. MỤC ĐÍCH\n")


def test_numbered_sentence_is_a_body_line_not_a_heading():
    rendered, chunks = _chunks([
        _h("2. Quy trình", 1),
        _p("2. Nhân viên nộp đơn đề nghị cho trưởng phòng xem xét và ký duyệt."),
    ])
    assert len(chunks) == 1 and chunks[0].section_path == ["2. Quy trình"]
    assert "Nhân viên nộp đơn" in chunks[0].content


def test_article_reference_inside_a_sentence_is_not_a_heading():
    sentence = "Điều 5 Luật Doanh nghiệp quy định về quyền của doanh nghiệp."
    _, chunks = _chunks([_h("Điều 1. Phạm vi", 1), _p("Căn cứ"), _p(sentence)])
    assert [c.section_path for c in chunks] == [["Điều 1. Phạm vi"]]
    assert sentence in chunks[0].content


def test_long_sentence_heading_from_the_converter_is_demoted_to_body():
    long_heading = "Căn cứ " + "quy định " * 20 + "của pháp luật hiện hành."
    _, chunks = _chunks([_h("1. Mục đích", 1), _h(long_heading, 2)])
    assert long_heading in chunks[0].content
    assert chunks[0].section_path == ["1. Mục đích"]


def test_converter_levels_win_when_a_hierarchy_is_reported():
    _, chunks = _chunks([_h("Chính sách", 1), _h("5.1 Chung", 2), _p("Nội dung.")],
                        file_type="MD", config=ChunkConfig(min_tokens=1))
    assert chunks[0].section_path == ["Chính sách", "5.1 Chung"]


def test_all_caps_lines_are_used_only_when_no_other_heading_exists():
    elements = [_p("PHẠM VI ÁP DỤNG"), _p("Áp dụng cho mọi phòng ban."), _p("QUY ĐỊNH CHUNG"),
                _p("Thực hiện theo quy trình.")]
    _, chunks = _chunks(elements, config=ChunkConfig(min_tokens=1))
    assert [c.section_path for c in chunks] == [["PHẠM VI ÁP DỤNG"], ["QUY ĐỊNH CHUNG"]]
    _, chunks = _chunks([_h("1. Mục đích")] + elements)
    assert all("PHẠM VI ÁP DỤNG" not in c.section_path for c in chunks)


def test_small_sections_merge_with_next_sibling_but_not_across_parents():
    _, chunks = _chunks([
        _h("1. Một", 1), _p("a b c."), _h("2. Hai", 1), _p("d e f."),
        _h("3. Ba", 1), _h("3.1 Con", 2), _p("g h i."),
        _h("4. Bốn", 1), _p("j k l."),
    ], config=ChunkConfig(min_tokens=64))
    assert chunks[0].section_path == ["1. Một"]
    assert "a b c." in chunks[0].content and "## 2. Hai" not in chunks[0].content
    assert "# 2. Hai" in chunks[0].content and "d e f." in chunks[0].content
    child = next(c for c in chunks if "g h i." in c.content)
    assert child.section_path == ["3. Ba", "3.1 Con"]


# -- families ---------------------------------------------------------------------------------


def test_family_detection():
    iso = [_h("1. Mục đích"), _p("x"), _h("2. Phạm vi"), _p("y")]
    legal = [_h(f"Điều {n}. Nội dung") for n in (1, 2, 3)]
    md = [_h("Cài đặt"), _p("x")]
    prose = [_p("Đoạn văn một."), _p("Đoạn văn hai.")]
    table = DocElement(kind="table", rows=[["Bước", "Trách nhiệm"], ["1", "A"]])
    for elements, family in ((iso, DocFamily.ISO_PROCEDURE), (legal, DocFamily.LEGAL_ARTICLES),
                             (md, DocFamily.MARKDOWN), (prose, DocFamily.PROSE),
                             ([_h("Chung"), table], DocFamily.ISO_PROCEDURE)):
        doc = StructuredDocument(file_type="MD", elements=elements)
        assert detect_family(render(doc).elements) is family


def test_legal_articles_stay_one_chunk_each_and_long_ones_split_on_clauses():
    clause = " ".join(["từ"] * 30)
    articles = []
    for n in (1, 2, 3):
        articles += [_h(f"Điều {n}. Quy định số {n}", 2), _p(f"Nội dung ngắn {n}.")]
    articles += [_h("Điều 4. Dài", 2)] + [_p(f"{k}. {clause}.") for k in range(1, 8)]
    rendered, chunks = _chunks(articles, file_type="MD",
                               config=ChunkConfig(target_tokens=80, max_tokens=100, min_tokens=64))
    short = [c for c in chunks if c.section_path[-1].startswith(("Điều 1", "Điều 2", "Điều 3"))]
    assert len(short) == 3
    long = [c for c in chunks if c.section_path[-1] == "Điều 4. Dài"]
    assert len(long) > 1
    assert all(c.content.lstrip().startswith(tuple("1234567")) for c in long)
    _check_invariants(rendered, chunks, ChunkConfig(target_tokens=80, max_tokens=100))


def test_prose_is_packed_by_paragraph_and_never_cut_inside_a_sentence():
    paragraphs = [_p(" ".join(f"w{i}x{j}" for j in range(12)) + ".") for i in range(10)]
    rendered, chunks = _chunks(paragraphs, file_type="MD",
                               config=ChunkConfig(target_tokens=40, max_tokens=50, min_tokens=1),
                               title="")
    assert len(chunks) == 4 and all(c.section_path == [] for c in chunks)
    assert all(c.content.endswith(".") for c in chunks)
    _check_invariants(rendered, chunks, ChunkConfig(max_tokens=50))


def test_one_oversized_paragraph_is_split_on_sentences_then_words():
    sentences = [" ".join(f"s{i}w{j}" for j in range(15)) + "." for i in range(6)]
    huge_word_run = " ".join(f"z{j}" for j in range(120))
    config = ChunkConfig(target_tokens=40, max_tokens=50, min_tokens=1)
    rendered, chunks = _chunks([_p(" ".join(sentences)), _p(huge_word_run)], file_type="MD",
                               config=config, title="")
    _check_invariants(rendered, chunks, config)
    assert all(c.content.endswith(".") for c in chunks[:3])
    assert " ".join(c.content for c in chunks[3:]).split() == huge_word_run.split()


def test_cuts_never_separate_a_combining_mark_from_its_base():
    decomposed = unicodedata.normalize("NFD", "ế" * 400)  # base letter + combining marks
    config = ChunkConfig(target_tokens=3, max_tokens=4, min_tokens=1)

    class ByChars:
        def count(self, text: str) -> int:
            return len(text) // 5 + 1

    doc = StructuredDocument(file_type="MD", elements=[_p(decomposed)])
    rendered = render(doc)
    chunks = chunk_document(rendered, ByChars(), config=config)
    assert len(chunks) > 1
    for c in chunks:
        assert not unicodedata.combining(c.content[0])
        assert unicodedata.is_normalized("NFD", c.content)


# -- procedure tables ---------------------------------------------------------------------------

PROC_ROWS = [
    ["Bước", "Trách nhiệm", "Mô tả", "Biểu mẫu"],
    ["1", "Nhân viên", "Lập đề nghị mua hàng", "BM-01"],
    ["2", "Trưởng phòng", "Xem xét đề nghị", ""],
    ["3", "Phòng mua", "Chọn nhà cung cấp", "BM-02"],
    ["4", "", "Ký hợp đồng", "BM-03"],
]


def _procedure(rows=PROC_ROWS, spans=None, pages=None):
    return DocElement(kind="table", rows=[list(r) for r in rows], cell_spans=spans, page=1,
                      row_pages=pages)


def test_each_procedure_row_is_a_chunk_with_headers_and_source_offsets():
    table = _procedure(pages=[1, 1, 1, 2, 2])
    table.page_end = 2
    rendered, chunks = _chunks([_h("1. Mục đích"), _p("Mô tả quy trình."), _h("2. Quy trình"),
                                table], pages=2, code="QT-MH-01")
    steps = [c for c in chunks if c.kind == "PROCEDURE_STEP"]
    assert [c.content for c in steps] == [
        "Bước: 1 | Trách nhiệm: Nhân viên | Mô tả: Lập đề nghị mua hàng | Biểu mẫu: BM-01",
        "Bước: 2 | Trách nhiệm: Trưởng phòng | Mô tả: Xem xét đề nghị",
        "Bước: 3 | Trách nhiệm: Phòng mua | Mô tả: Chọn nhà cung cấp | Biểu mẫu: BM-02",
        "Bước: 4 | Mô tả: Ký hợp đồng | Biểu mẫu: BM-03",
    ]
    el = next(e for e in rendered.elements if e.kind == "table")
    for step, (start, end), page in zip(steps, el.row_spans[1:], [1, 1, 2, 2], strict=True):
        assert (step.char_start, step.char_end) == (start, end)
        assert step.page_start == step.page_end == page
        assert rendered.markdown[start:end].startswith("|")
    assert steps[0].index_text.startswith(
        "Quy trình mua hàng [QT-MH-01] › 2. Quy trình\nBước: 1 |")
    assert detect_family(rendered.elements) is DocFamily.ISO_PROCEDURE
    _check_invariants(rendered, chunks)


def test_merged_responsibility_cell_is_repeated_down_each_covered_row():
    rows = [["Bước", "Trách nhiệm", "Mô tả", "Biểu mẫu"],
            ["1", "Nhân viên", "Lập đề nghị", "BM-01"],
            ["2", "", "Gửi đề nghị", ""],
            ["3", "Phòng mua", "Chọn nhà cung cấp", ""],
            ["4", "", "Ký hợp đồng", ""]]
    with_spans, _ = _chunks([_procedure(rows, spans=[(1, 1, 2, 1)])], file_type="MD")[0], None
    chunks = chunk_document(with_spans, Words(), title="T")
    owners = [c.content for c in chunks]
    assert "Trách nhiệm: Nhân viên" in owners[1]  # row 2 inherits the merged cell
    assert "Trách nhiệm" not in owners[3]  # row 4 is not covered by any span
    rendered = _chunks([_procedure(rows, spans=None)], file_type="MD")[0]
    unknown = chunk_document(rendered, Words(), title="T")
    assert "Trách nhiệm" not in unknown[1].content  # no spans: nothing is guessed
    md = with_spans.markdown
    assert md.count("Nhân viên") == 1  # the rendered Markdown still writes the value once


def test_procedure_chunk_over_budget_is_split_but_keeps_the_row_offsets():
    rows = [["Bước", "Trách nhiệm", "Mô tả"],
            ["1", "A", " ".join(f"mô{j}" for j in range(60)) + "."]]
    config = ChunkConfig(target_tokens=20, max_tokens=24, min_tokens=1)
    rendered, chunks = _chunks([_procedure(rows)], file_type="MD", config=config, title="")
    assert len(chunks) > 1 and {c.kind for c in chunks} == {"PROCEDURE_STEP"}
    assert len({(c.char_start, c.char_end) for c in chunks}) == 1
    assert all(c.token_count <= 24 for c in chunks)


def test_long_regular_table_is_cut_by_row_with_header_repeated():
    rows = [["Mã", "Tên"]] + [[f"M{i}", f"mặt hàng số {i}"] for i in range(1, 21)]
    table = DocElement(kind="table", rows=rows, page=1, row_pages=[1] * 10 + [2] * 11, page_end=2)
    config = ChunkConfig(target_tokens=30, max_tokens=40, min_tokens=1)
    rendered, chunks = _chunks([_h("Danh mục"), table], pages=2, config=config)
    parts = [c for c in chunks if c.kind == "TABLE"]
    assert len(parts) > 2
    for part in parts:
        assert part.content.startswith("| Mã | Tên |\n| --- | --- |\n")
        assert part.token_count <= 40
    el = next(e for e in rendered.elements if e.kind == "table")
    assert parts[0].char_start == el.row_spans[1][0]
    assert parts[-1].char_end == el.row_spans[-1][1]
    assert parts[0].page_start == 1 and parts[-1].page_end == 2
    rows_seen = [line for p in parts for line in p.content.splitlines()[2:]]
    assert len(rows_seen) == 20


# -- index text, tokenizer, errors -------------------------------------------------------------


def test_index_prefix_forms():
    assert index_prefix("Mua hàng", "QT-01", ["5. A", "5.1 B"]) == "Mua hàng [QT-01] › 5. A › 5.1 B"
    assert index_prefix("Mua hàng", None, ["5. A"]) == "Mua hàng › 5. A"
    assert index_prefix("Mua hàng", "", []) == "Mua hàng"
    assert index_prefix("", "QT-01", []) == "[QT-01]"


def test_index_text_has_code_only_when_extracted_and_never_revision_or_date():
    elements = [_h("1. Mục đích"), _p("Nội dung.")]
    _, with_code = _chunks(elements, code="QT-MH-01")
    _, without = _chunks(elements)
    assert with_code[0].index_text == "Quy trình mua hàng [QT-MH-01] › 1. Mục đích\nNội dung."
    assert without[0].index_text == "Quy trình mua hàng › 1. Mục đích\nNội dung."


def test_prefix_counts_toward_max_tokens():
    config = ChunkConfig(target_tokens=10, max_tokens=12, min_tokens=1)
    title = "Tên tài liệu rất dài " * 2  # 10 whitespace tokens of prefix with the path
    paragraph = _p(" ".join(f"t{i}" for i in range(30)) + ".")
    rendered, chunks = _chunks([_h("A"), paragraph], file_type="MD", title=title, config=config)
    _check_invariants(rendered, chunks, config)
    assert len(chunks) > 1


def test_empty_document_raises_empty_content():
    doc = StructuredDocument(file_type="MD", elements=[
        DocElement(kind="paragraph", text="x", role="boilerplate")])
    with pytest.raises(ExtractionError) as error:
        chunk_document(render(doc), Words())
    assert error.value.code is FailureCode.EMPTY_CONTENT


def test_hf_tokenizer_loads_by_model_and_revision_without_model_weights(monkeypatch):
    calls = []

    class FakeTokenizer:
        def encode(self, text, add_special_tokens=True):
            calls.append(add_special_tokens)
            return text.split()

    class FakeAuto:
        @staticmethod
        def from_pretrained(model, revision=None):
            calls.append((model, revision))
            return FakeTokenizer()

    module = types.ModuleType("transformers")
    module.AutoTokenizer = FakeAuto
    monkeypatch.setitem(sys.modules, "transformers", module)
    tokenizer = HFTokenizer("intfloat/multilingual-e5-large", "abc123")
    assert tokenizer.count("một hai ba") == 3
    assert calls == [("intfloat/multilingual-e5-large", "abc123"), False]


# -- end to end and properties -------------------------------------------------------------------


def test_markdown_file_end_to_end_with_cleaning():
    source = """---
doc_code: HR-01
---
# Chính sách nghỉ phép

## 1. Mục đích

Quy định cách tính ngày nghỉ.

## 2. Quy trình

| Bước | Trách nhiệm | Mô tả |
|---|---|---|
| 1 | Nhân viên | Gửi đề nghị |
| 2 | Quản lý | Phê duyệt |
"""
    doc = extract(source.encode("utf-8"), "policy.md")
    result = clean_document(doc)
    rendered = render(result.document)
    chunks = chunk_document(rendered, Words(), title="Chính sách nghỉ phép",
                            doc_code=result.meta.doc_code)
    assert result.meta.doc_code == "HR-01"
    assert [c.kind for c in chunks] == ["TEXT", "PROCEDURE_STEP", "PROCEDURE_STEP"]
    assert chunks[1].index_text.startswith(
        "Chính sách nghỉ phép [HR-01] › Chính sách nghỉ phép › 2. Quy trình\nBước: 1")
    _check_invariants(rendered, chunks)
    assert all(c.page_start is None for c in chunks)


_word = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), max_codepoint=0x24F),
    min_size=1, max_size=8)


@st.composite
def _body(draw):
    elements = []
    for _ in range(draw(st.integers(1, 12))):
        kind = draw(st.sampled_from(["h", "p", "p", "p", "t"]))
        words = draw(st.lists(_word, min_size=1, max_size=40))
        text = " ".join(words) + draw(st.sampled_from(["", ".", "?"]))
        if kind == "h":
            elements.append(_h(text, draw(st.integers(1, 3))))
        elif kind == "t":
            n = draw(st.integers(2, 8))
            elements.append(DocElement(kind="table", rows=[["Mã", "Tên"]] + [
                [f"m{i}", " ".join(words[:5])] for i in range(n)]))
        else:
            elements.append(_p(text))
    return elements


@settings(max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(_body(), st.integers(8, 40))
def test_property_chunks_are_substrings_within_budget(elements, max_tokens):
    config = ChunkConfig(target_tokens=max(max_tokens - 4, 1), max_tokens=max_tokens,
                         min_tokens=5)
    doc = StructuredDocument(file_type="MD", elements=elements)
    rendered = render(doc)
    try:
        chunks = chunk_document(rendered, Words(), title="T", config=config)
    except ExtractionError:
        return
    for c in chunks:
        assert rendered.markdown[c.char_start:c.char_end] == c.content or c.kind == "TABLE"
        assert c.token_count <= max_tokens
        assert c.content.strip()
    ordered = [c.char_start for c in chunks]
    assert ordered == sorted(ordered)
