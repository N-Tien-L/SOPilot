"""V2-47 items 4 and 5a: a table of contents is not chunked; legal preamble fragments merge."""
from __future__ import annotations

from sopilot_ai.docproc import (
    ChunkConfig,
    DocElement,
    DocFamily,
    StructuredDocument,
    chunk_document,
    render,
)


class Words:
    """Whitespace tokenizer: deterministic and independent of any model download."""

    def count(self, text: str) -> int:
        return len(text.split())


def _h(text: str, level: int = 1) -> DocElement:
    return DocElement(kind="heading", text=text, level=level)


def _p(text: str) -> DocElement:
    return DocElement(kind="paragraph", text=text)


def _li(number: str, text: str) -> DocElement:
    return DocElement(kind="list_item", text=text, number=number)


def _run(elements, family, config=None):
    rendered = render(StructuredDocument(file_type="PDF", elements=elements, page_count=1))
    chunks = chunk_document(rendered, Words(), title="Tài liệu", config=config, family=family)
    _check_invariants(rendered, chunks, config)
    return rendered, chunks


def _check_invariants(rendered, chunks, config=None):
    """The same invariants as ``test_chunk._check_invariants``."""
    config = config or ChunkConfig()
    for c in chunks:
        assert c.token_count == len(c.index_text.split()) <= config.max_tokens
        assert 0 <= c.char_start < c.char_end <= len(rendered.markdown)
        if c.kind == "TEXT":
            assert rendered.markdown[c.char_start:c.char_end] == c.content


def _overlaps(chunks, start: int, end: int) -> bool:
    return any(c.char_start < end and start < c.char_end for c in chunks)


BODY = " ".join(f"từ{i}" for i in range(30)) + "."
TOC_TITLES = ["MỤC ĐÍCH", "PHẠM VI", "TÀI LIỆU VIỆN DẪN", "ĐỊNH NGHĨA/VIẾT TẮT", "NỘI DUNG",
              "BIỂU MẪU", "HỒ SƠ CẦN LƯU"]


def _qt05() -> list[DocElement]:
    """tb-qt05 after the outline: the contents heading, a line, seven promoted list items."""
    return [
        _h("MỤC LỤC"),
        _p("BẢNG THEO DÕI SỬA ĐỔI TÀI LIỆU DANH SÁCH PHÂN PHỐI TÀI LIỆU"),
        *[_li(f"{n}.", title) for n, title in enumerate(TOC_TITLES, start=1)],
        _h("DANH SÁCH PHÂN PHỐI TÀI LIỆU:"),
        _p("Quy trình này được phân phối trong Phòng Kế hoạch."),
        DocElement(kind="table", rows=[["Nơi nhận", "Số lượng"], ["Phòng Kế hoạch", "1"]]),
        _h("1. MỤC ĐÍCH"),
        _p("Quy định cách mua hàng. " + BODY),
    ]


# -- item 4: table of contents -----------------------------------------------------------------


def test_a_table_of_contents_produces_no_chunk():
    elements = _qt05()
    rendered, chunks = _run(elements, DocFamily.ISO_PROCEDURE)
    toc = rendered.elements[:9]  # heading, line, seven items
    assert [e.text for e in toc[2:]] == TOC_TITLES
    for el in toc:
        assert not _overlaps(chunks, el.char_start, el.char_end)
    assert not any("MỤC LỤC" in c.content or "TÀI LIỆU VIỆN DẪN" in c.content for c in chunks)
    assert rendered.markdown.startswith("# MỤC LỤC\n\n")
    assert "6. BIỂU MẪU" in rendered.markdown


def test_the_section_after_a_table_of_contents_is_still_chunked():
    _, chunks = _run(_qt05(), DocFamily.ISO_PROCEDURE)
    assert any("Quy trình này được phân phối" in c.content for c in chunks)
    assert any("Quy định cách mua hàng." in c.content for c in chunks)


def test_an_english_contents_heading_with_list_items_is_skipped():
    elements = [
        _h("Table of contents"),
        _li("1.", "Purpose"), _li("2.", "Scope"), _li("3.", "Procedure"),
        _h("1. Purpose"), _p("This procedure covers purchasing. " + BODY),
    ]
    rendered, chunks = _run(elements, DocFamily.ISO_PROCEDURE)
    assert not any("Scope" in c.content or "Table of contents" in c.content for c in chunks)
    assert any("This procedure covers purchasing." in c.content for c in chunks)
    assert "Scope" in rendered.markdown


def test_a_contents_heading_followed_by_prose_is_chunked():
    elements = [
        _h("Contents"),
        _p("This chapter explains how purchase requests are approved by the department head."),
        _h("1. Purpose"), _p("Purchasing. " + BODY),
    ]
    _, chunks = _run(elements, DocFamily.ISO_PROCEDURE, ChunkConfig(min_tokens=1))
    assert any("explains how purchase requests" in c.content for c in chunks)


def test_a_contents_heading_with_a_table_is_chunked():
    table = DocElement(kind="table", rows=[["Mục", "Trang"], ["Mục đích", "1"]])
    elements = [_h("MỤC LỤC"), _li("1.", "Mục đích"), _li("2.", "Phạm vi"), table,
                _h("1. Mục đích"), _p("Nội dung. " + BODY)]
    _, chunks = _run(elements, DocFamily.ISO_PROCEDURE, ChunkConfig(min_tokens=1))
    assert any("| Mục | Trang |" in c.content for c in chunks)


def test_numbered_procedure_steps_under_a_normal_heading_are_chunked():
    elements = [
        _h("5. NỘI DUNG"),
        _li("1.", "Nhân viên lập đề nghị"), _li("2.", "Trưởng phòng xem xét"),
        _li("3.", "Phòng mua chọn nhà cung cấp"),
        _h("6. BIỂU MẪU"), _p("Biểu mẫu BM-01. " + BODY),
    ]
    _, chunks = _run(elements, DocFamily.ISO_PROCEDURE, ChunkConfig(min_tokens=1))
    joined = "\n".join(c.content for c in chunks)
    assert "Nhân viên lập đề nghị" in joined and "Phòng mua chọn nhà cung cấp" in joined


def test_a_single_entry_contents_section_is_not_a_table_of_contents():
    elements = [_h("Contents"), _li("1.", "Purpose of this document."),
                _h("1. Purpose"), _p("Text. " + BODY)]
    _, chunks = _run(elements, DocFamily.MARKDOWN, ChunkConfig(min_tokens=1))
    assert any("Purpose of this document." in c.content for c in chunks)


# -- item 5a: legal preamble ----------------------------------------------------------------


def _vbhn109() -> list[DocElement]:
    return [
        _p("Số:"),
        _h("VĂN BẢN HỢP NHẤT"),
        _p("/2026/VBHN-NĐ-NHNN"),
        _p("Hà Nội, ngày 1 tháng 1 năm 2026"),
        _h("NGHỊ ĐỊNH"),
        _h("Về quản lý vay nước ngoài"),
        _p("Căn cứ Luật Ngân hàng Nhà nước;"),
        _p("Căn cứ Luật Các tổ chức tín dụng;"),
        _h("Chương I"),
        _h("QUY ĐỊNH CHUNG"),
        _h("Điều 1. Phạm vi điều chỉnh", 3),
        _p("Nghị định này quy định về việc vay."),
        _h("Điều 2. Đối tượng áp dụng", 3),
        _p("Áp dụng cho mọi tổ chức."),
        _h("Điều 3. Giải thích từ ngữ", 3),
        _p("Trong Nghị định này, các từ ngữ được hiểu như sau."),
    ]


def test_legal_preamble_fragments_merge_into_the_next_section():
    _, chunks = _run(_vbhn109(), DocFamily.LEGAL_ARTICLES)
    assert not any(c.content.strip() in ("Số:", "/2026/VBHN-NĐ-NHNN") for c in chunks)
    holder = next(c for c in chunks if "Số:" in c.content)
    assert "/2026/VBHN-NĐ-NHNN" in holder.content


def test_legal_preamble_never_merges_into_the_first_article():
    rendered, chunks = _run(_vbhn109(), DocFamily.LEGAL_ARTICLES)
    article = next(e for e in rendered.elements if e.text == "Điều 1. Phạm vi điều chỉnh")
    before = [c for c in chunks if c.char_start < article.char_start]
    assert before
    assert all(c.char_end <= article.char_start for c in before)
    own = next(c for c in chunks if "Nghị định này quy định về việc vay." in c.content)
    assert own.section_path[-1] == "Điều 1. Phạm vi điều chỉnh"
    assert own.char_start >= article.char_end


def test_articles_are_never_merged_with_each_other_even_when_short():
    rendered, chunks = _run(_vbhn109(), DocFamily.LEGAL_ARTICLES)
    articles = [e for e in rendered.elements
                if e.kind == "heading" and e.text.startswith("Điều")]
    assert len(articles) == 3
    for chunk in chunks:
        inside = [a for a in articles
                  if chunk.char_start <= a.char_start and a.char_end <= chunk.char_end]
        assert len(inside) <= 1
    for needle in ("quy định về việc vay.", "Áp dụng cho mọi tổ chức.", "các từ ngữ được hiểu"):
        holders = [c for c in chunks if needle in c.content]
        assert len(holders) == 1
        assert holders[0].section_path[-1].startswith("Điều")


LONG = (" nội dung điều này là một câu dài hơn một trăm ký tự để không bị đọc thành tiêu đề"
        " của một mục nào cả.")


def _qd1308() -> list[DocElement]:
    return [
        _p("_____________________________________"),
        _p("Hà Nội, ngày 18 tháng 7 năm 2026"),
        _h("QUYẾT ĐỊNH Phê duyệt Chiến lược dữ liệu quốc gia"),
        _p("___________"),
        _h("THỦ TƯỚNG CHÍNH PHỦ"),
        _p("Căn cứ Luật Tổ chức Chính phủ;"),
        _p("Căn cứ Nghị định số 1/2026/NĐ-CP;"),
        _h("QUYẾT ĐỊNH:"),
        _p("Điều 1. Phê duyệt Chiến lược dữ liệu quốc gia." + LONG),
        _p("Điều 2. Quyết định này có hiệu lực." + LONG),
        _p("Điều 3. Các bộ trưởng thi hành." + LONG),
    ]


def test_preamble_cutoff_is_the_first_article_line_when_articles_are_body_lines():
    rendered, chunks = _run(_qd1308(), DocFamily.LEGAL_ARTICLES)
    assert not any(set(c.content.strip()) <= {"_"} for c in chunks)
    preamble = next(c for c in chunks if "Hà Nội, ngày 18 tháng 7 năm 2026" in c.content)
    assert "Căn cứ Nghị định số 1/2026/NĐ-CP;" in preamble.content
    assert "Điều 1." not in preamble.content
    cutoff = next(e for e in rendered.elements if e.text == "QUYẾT ĐỊNH:")
    assert preamble.char_end <= cutoff.char_start
    article = next(c for c in chunks if "Điều 1. Phê duyệt" in c.content)
    assert article.section_path == ["QUYẾT ĐỊNH:"]
    assert article.char_start >= cutoff.char_end


def test_a_text_chunk_with_no_letters_is_dropped_in_legal_documents():
    elements = _vbhn109() + [_h("Điều 4. Hiệu lực", 3), _p("__________")]
    rendered, chunks = _run(elements, DocFamily.LEGAL_ARTICLES)
    assert not any(c.kind == "TEXT" and not any(ch.isalpha() for ch in c.content)
                   for c in chunks)
    underscores = next(e for e in rendered.elements if e.text == "__________")
    assert not _overlaps(chunks, underscores.char_start, underscores.char_end)
    assert any("Áp dụng cho mọi tổ chức." in c.content for c in chunks)


def test_a_numeric_table_is_kept_in_legal_documents():
    table = DocElement(kind="table", rows=[["1", "2"], ["3", "4"]])
    elements = _vbhn109() + [_h("Điều 4. Biểu phí", 3), table]
    rendered, chunks = _run(elements, DocFamily.LEGAL_ARTICLES)
    element = next(e for e in rendered.elements if e.kind == "table")
    kept = [c for c in chunks
            if c.char_start < element.char_end and element.char_start < c.char_end]
    assert kept and "| 3 | 4 |" in kept[0].content


def test_a_no_letter_text_chunk_is_kept_outside_legal_documents():
    elements = [_h("Phụ lục"), _p("__________")]
    _, chunks = _run(elements, DocFamily.MARKDOWN)
    assert [c.content for c in chunks] == ["__________"]


def test_other_families_keep_the_sibling_only_merge_rule():
    elements = [_p("Số:"), _h("VĂN BẢN"), _p("/2026/X"), _h("1. Một"), _p("a b c.")]
    _, chunks = _run(elements, DocFamily.MARKDOWN)
    assert any(c.content.strip() == "Số:" for c in chunks)


def test_a_numbered_contents_section_is_chunked():
    elements = [
        _h("1. Purpose"), _p("Kit check. " + BODY),
        _h("6. Contents"), _li("1.", "Sterile gloves"), _li("2.", "Swab, 2 pcs"),
        _h("7. Storage"), _p("Keep dry. " + BODY),
    ]
    _, chunks = _run(elements, DocFamily.ISO_PROCEDURE, ChunkConfig(min_tokens=1))
    joined = " ".join(c.content for c in chunks)
    assert "Sterile gloves" in joined and "Swab, 2 pcs" in joined


def test_a_table_of_contents_after_a_small_section_does_not_widen_that_sections_chunk():
    elements = [
        _h("QUY TRÌNH X"), _p("Quy trình mua hàng nội bộ."),
        _h("MỤC LỤC"), _li("1.", "Mục đích kèm theo mô tả dài."), _li("2.", "Phạm vi áp dụng."),
        _li("3.", "MỤC ĐÍCH"), _li("4.", "PHẠM VI"),
        _h("DANH SÁCH PHÂN PHỐI TÀI LIỆU:"), _p("Phân phối cho Phòng Kế hoạch."),
    ]
    rendered, chunks = _run(elements, DocFamily.ISO_PROCEDURE)
    toc = [e for e in rendered.elements[2:7]]
    assert [e.text for e in toc][0] == "MỤC LỤC"
    start, end = toc[0].char_start, toc[-1].char_end
    assert not _overlaps(chunks, start, end)
    assert any("Quy trình mua hàng nội bộ." in c.content for c in chunks)
    assert any("Phân phối cho Phòng Kế hoạch." in c.content for c in chunks)
    assert not any("MỤC ĐÍCH" in c.content or "Phạm vi áp dụng." in c.content for c in chunks)


PROC_ROWS = [
    ["Bước", "Trách nhiệm", "Mô tả", "Biểu mẫu"],
    ["1", "Nhân viên", "Lập đề nghị mua hàng", "BM-01"],
    ["2", "Trưởng phòng", "Xem xét đề nghị", ""],
]


def test_a_legal_preamble_section_with_a_procedure_table_is_not_merged():
    table = DocElement(kind="table", rows=[list(r) for r in PROC_ROWS], page=1)
    elements = [
        _h("PHẦN MỞ ĐẦU"), _p("Lời nói đầu ngắn."),
        _h("QUY TRÌNH XỬ LÝ"), table,
        _h("Điều 1. Phạm vi", 3), _p("Áp dụng cho mọi tổ chức."),
        _h("Điều 2. Đối tượng", 3), _p("Đối tượng là cán bộ."),
        _h("Điều 3. Hiệu lực", 3), _p("Có hiệu lực từ ngày ký."),
    ]
    _, chunks = _run(elements, DocFamily.LEGAL_ARTICLES)
    steps = [c for c in chunks if c.kind == "PROCEDURE_STEP"]
    assert len(steps) == 2
    assert all(c.section_path[-1] == "QUY TRÌNH XỬ LÝ" for c in steps)
    intro = next(c for c in chunks if "Lời nói đầu ngắn." in c.content)
    assert intro.kind == "TEXT" and intro.section_path == ["PHẦN MỞ ĐẦU"]
    assert "QUY TRÌNH XỬ LÝ" not in intro.content


def test_the_merge_barrier_survives_an_absorbed_section():
    elements = [
        _h("1. Một"), _p("a b c."),
        _h("2. Hai"), _p("d e f."),
        _h("MỤC LỤC"), _li("1.", "Mục đích kèm theo mô tả dài."), _li("2.", "Phạm vi áp dụng."),
        _h("3. Ba"), _p("g h i."),
    ]
    rendered, chunks = _run(elements, DocFamily.MARKDOWN)
    toc = rendered.elements[4:7]
    assert toc[0].text == "MỤC LỤC"
    assert not _overlaps(chunks, toc[0].char_start, toc[-1].char_end)
    first = next(c for c in chunks if "a b c." in c.content)
    assert "d e f." in first.content  # B was absorbed into A
    assert "g h i." not in first.content
    assert any("g h i." in c.content for c in chunks)
