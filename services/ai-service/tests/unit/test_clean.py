from __future__ import annotations

import pytest

from sopilot_ai.docproc import DocElement, StructuredDocument, render
from sopilot_ai.docproc.clean import CleanConfig, clean_document
from sopilot_ai.docproc.clean.metadata import parse_date


def _p(text: str, page: int, **kw) -> DocElement:
    return DocElement(kind="paragraph", text=text, page=page, **kw)


def _h(text: str, page: int, level: int = 1) -> DocElement:
    return DocElement(kind="heading", text=text, level=level, page=page)


def _pdf(elements: list[DocElement], pages: int) -> StructuredDocument:
    return StructuredDocument(file_type="PDF", elements=elements, page_count=pages)


def _codes(result) -> list[str]:
    return [w.code for w in result.warnings]


_WORDS = {1: "một", 2: "hai", 3: "ba", 4: "bốn"}


def _repeating_pdf(pages: int = 4) -> StructuredDocument:
    elements = [_h("1. Mục đích", 1)]
    for page in range(1, pages + 1):
        elements.insert(len(elements) if page > 1 else 0, _p("CÔNG TY ABC - QT-MH-01", page))
        elements.append(_p(f"Nội dung riêng của trang {_WORDS[page]} nói về quy trình.", page))
        elements.append(_p(f"Trang {page}/{pages}", page))
    return _pdf(elements, pages)


def test_repeated_header_and_footer_are_removed_with_page_numbers_masked():
    result = clean_document(_repeating_pdf())
    md = render(result.document).markdown
    assert "CÔNG TY ABC" not in md and "Trang 1/4" not in md
    assert "Nội dung riêng của trang ba" in md
    kinds = {b.kind for b in result.boilerplate}
    assert kinds == {"header", "footer"}
    assert all(b.page for b in result.boilerplate) and len(result.boilerplate) == 8


def test_first_heading_is_never_a_header_even_when_it_repeats_on_every_page():
    elements = []
    for page in range(1, 5):
        elements += [_h("Quy trình mua hàng", page), _p(f"Đoạn nội dung số {page}.", page)]
    result = clean_document(_pdf(elements, 4))
    assert result.document.elements[0].role == "content"
    assert [e.role for e in result.document.elements[2::2]] == ["header"] * 3


@pytest.mark.parametrize("pages", [1, 2])
def test_short_pdfs_lose_nothing(pages):
    elements = []
    for page in range(1, pages + 1):
        elements += [_h(f"Tiêu đề {page}", page), _p(f"Đoạn cuối của trang {page}.", page)]
    result = clean_document(_pdf(elements, pages))
    assert all(e.role == "content" for e in result.document.elements)
    assert result.boilerplate == []
    assert "BOILERPLATE_REMOVED" not in _codes(result)


def test_min_pages_threshold_is_configurable():
    doc = _repeating_pdf(2)
    assert clean_document(doc).boilerplate == []
    assert clean_document(doc, CleanConfig(header_footer_min_pages=2)).boilerplate


def test_long_paragraph_repeated_on_every_page_is_content():
    text = "Lưu ý quan trọng. " * 20
    elements = [_p(text, p) for p in range(1, 5)]
    assert clean_document(_pdf(elements, 4)).boilerplate == []


FRAME_PDF = [
    _p("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", 1),
    _p("Độc lập - Tự do - Hạnh phúc", 1),
    _p("Số: 30/2020/NĐ-CP", 1),
    _h("Điều 1. Phạm vi", 1),
    _p("Nghị định này quy định về công tác văn thư.", 1),
    _p("Nơi nhận:", 2),
    DocElement(kind="list_item", text="Như Điều 3;", page=2),
    DocElement(kind="list_item", text="Lưu: VT.", page=2),
    _p("TM. CHÍNH PHỦ", 2),
    _p("THỦ TƯỚNG", 2),
    _p("Nguyễn Văn A", 2),
]


def test_vietnamese_administrative_frame_is_separated_and_body_kept():
    result = clean_document(_pdf([e.model_copy() for e in FRAME_PDF], 2))
    md = render(result.document).markdown
    assert md == "## Điều 1. Phạm vi\n\nNghị định này quy định về công tác văn thư.".replace(
        "## ", "# ")
    kinds = [b.kind for b in result.boilerplate]
    assert kinds == ["national_motto", "national_motto", "document_number", "recipients",
                     "recipients", "recipients", "signature", "signature", "signature"]
    assert result.meta.doc_code == "30/2020/NĐ-CP"
    assert "BOILERPLATE_REMOVED" in _codes(result)


def test_body_paragraph_that_looks_like_a_signature_word_is_kept():
    elements = [_h("Quy định", 1), _p("Ký tên vào biên bản khi bàn giao tài sản cho phòng ban.", 1),
                _p("Kỳ họp tiếp theo diễn ra vào tháng sau.", 1)]
    result = clean_document(_pdf(elements, 1))
    assert result.boilerplate == []


APPROVAL = DocElement(kind="table", page=1, rows=[
    ["", "Soạn thảo", "Soát xét", "Phê duyệt"],
    ["Họ tên", "Nguyễn A", "Trần B", "Lê Văn C"],
    ["Chức vụ", "Chuyên viên", "Trưởng phòng", "Giám đốc"],
])
REVISIONS = DocElement(kind="table", page=1, rows=[
    ["Lần sửa đổi", "Ngày", "Nội dung sửa đổi"],
    ["01", "01/01/2020", "Ban hành lần đầu"],
    ["02", "15/03/2022", "Bổ sung bước 4"],
])


def test_approval_and_revision_tables_leave_the_body_but_feed_metadata():
    elements = [
        _h("Quy trình mua hàng", 1),
        _p("Mã số: QT-MH-01", 1), _p("Lần ban hành: 02", 1),
        _p("Ngày hiệu lực: 15/03/2022", 1), APPROVAL.model_copy(),
        _h("Theo dõi sửa đổi", 1, 2), REVISIONS.model_copy(),
        _h("1. Mục đích", 1), _p("Quy định việc mua hàng.", 1),
    ]
    result = clean_document(_pdf(elements, 1))
    md = render(result.document).markdown
    assert md == "# Quy trình mua hàng\n\n# 1. Mục đích\n\nQuy định việc mua hàng."
    meta = result.meta
    assert (meta.doc_code, meta.revision_label) == ("QT-MH-01", "02")
    assert meta.effective_date == "2022-03-15"
    assert meta.approved_by == "Lê Văn C"
    assert meta.model_dump(by_alias=True)["docCode"] == "QT-MH-01"
    kinds = {b.kind for b in result.boilerplate}
    assert {"approval_table", "revision_table"} <= kinds
    assert "Phê duyệt" in next(b.text for b in result.boilerplate if b.kind == "approval_table")


def test_metadata_prefers_labels_then_code_shape_in_header():
    doc = _pdf([_p("SOP-QA-017 | Rev. 3 | Effective date: 2024-05-02", 1),
                _h("1. Purpose", 1), _p("Why.", 1)], 1)
    meta = clean_document(doc).meta
    assert (meta.doc_code, meta.revision_label, meta.effective_date) == (
        "SOP-QA-017", "3", "2024-05-02")


def test_markdown_frontmatter_feeds_metadata():
    doc = StructuredDocument(file_type="MD", elements=[_h("Quy trình", 0).model_copy(
        update={"page": None})], frontmatter={"doc_code": "HR-01", "effective_date": "2023-01-09",
                                               "version": 4})
    meta = clean_document(doc).meta
    assert (meta.doc_code, meta.revision_label, meta.effective_date) == ("HR-01", "4",
                                                                         "2023-01-09")


@pytest.mark.parametrize("text, expected", [
    ("ngày 05 tháng 3 năm 2021", "2021-03-05"),
    ("05/03/2021", "2021-03-05"),
    ("2021-03-05", "2021-03-05"),
    ("31/02/2021", None),
    ("không có ngày", None),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_each_warning_code_has_a_fixture_and_clean_fixture_has_none():
    clean = _pdf([_h("Tiêu đề", 1), _p("Nội dung đủ dài để vượt ngưỡng ký tự tối thiểu.", 1),
                  _h("Mục 2", 2), _p("Nội dung trang hai cũng đủ dài để vượt ngưỡng.", 2)], 2)
    assert clean_document(clean).warnings == []

    empty_page = _pdf([_h("Tiêu đề", 1), _p("Nội dung đủ dài để vượt ngưỡng ký tự tối thiểu.", 1)],
                      3)
    warning = next(w for w in clean_document(empty_page).warnings
                   if w.code == "PAGES_WITHOUT_TEXT")
    assert warning.pages == [2, 3]

    glyphs = _pdf([_h("Tiêu đề", 1), _p("Chữ lỗi � và (cid:12) và  trong đoạn này.", 1)],
                  1)
    warning = next(w for w in clean_document(glyphs).warnings if w.code == "UNMAPPED_GLYPHS")
    assert warning.count == 3 and warning.pages == [1]

    no_headings = _pdf([_p("Đoạn một đủ dài để qua ngưỡng ký tự tối thiểu.", 1),
                        _p("Đoạn hai đủ dài để qua ngưỡng ký tự tối thiểu.", 2)], 2)
    assert "NO_HEADINGS_DETECTED" in _codes(clean_document(no_headings))

    note = clean.model_copy(update={"converter_warnings": [{"kind": "PARTIAL_SUCCESS",
                                                           "pages": []}]})
    warning = next(w for w in clean_document(note).warnings if w.code == "CONVERTER_WARNING")
    assert warning.kind == "PARTIAL_SUCCESS"


def test_one_page_pdf_without_headings_is_not_flagged():
    doc = _pdf([_p("Một trang văn xuôi đủ dài để vượt ngưỡng ký tự tối thiểu.", 1)], 1)
    assert clean_document(doc).warnings == []


def test_markdown_without_headings_is_flagged_only_when_longer_than_max_tokens():
    class Words:
        def count(self, text: str) -> int:
            return len(text.split())

    doc = StructuredDocument(file_type="MD", elements=[
        DocElement(kind="paragraph", text="từ " * 600)])
    assert "NO_HEADINGS_DETECTED" in _codes(clean_document(doc, tokenizer=Words()))
    assert clean_document(doc).warnings == []
    short = StructuredDocument(file_type="MD", elements=[DocElement(kind="paragraph", text="a b")])
    assert clean_document(short, tokenizer=Words()).warnings == []


def test_cleaning_does_not_mutate_the_input_document():
    doc = _repeating_pdf()
    clean_document(doc)
    assert all(e.role == "content" for e in doc.elements)


def test_boilerplate_never_reaches_the_rendered_markdown():
    doc = _pdf([e.model_copy() for e in FRAME_PDF] + [APPROVAL.model_copy()], 2)
    result = clean_document(doc)
    md = render(result.document).markdown
    for block in result.boilerplate:
        for line in block.text.splitlines():
            assert line not in md
