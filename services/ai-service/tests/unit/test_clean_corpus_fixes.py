"""Regression fixtures for the cleaning faults found on the V2-19 corpus (V2-21/V2-22, 2026-11-03).

Synthetic, short and Docling-free: each test rebuilds the element shape the extractor produced
for one family of documents, without copying any document's text.
"""
from __future__ import annotations

from sopilot_ai.docproc import ChunkConfig, DocElement, StructuredDocument, chunk_document, render
from sopilot_ai.docproc.clean import clean_document


class Words:
    def count(self, text: str) -> int:
        return len(text.split())


def _p(text: str, page: int, kind: str = "paragraph", **kw) -> DocElement:
    return DocElement(kind=kind, text=text, page=page, **kw)


def _h(text: str, page: int) -> DocElement:
    return DocElement(kind="heading", text=text, level=1, page=page)


def _t(rows: list[list[str]], page: int, header_rows: int = 0) -> DocElement:
    return DocElement(kind="table", rows=rows, page=page, header_rows=header_rows,
                      row_pages=[page] * len(rows))


def _pdf(elements: list[DocElement], pages: int) -> StructuredDocument:
    return StructuredDocument(file_type="PDF", elements=elements, page_count=pages)


_BODY = ["Nhân viên lập phiếu đề nghị và gửi trưởng phòng.",
         "Trưởng phòng xem xét trong hai ngày làm việc.",
         "Kế toán đối chiếu chứng từ trước khi thanh toán.",
         "Thủ kho nhận hàng và ghi sổ theo dõi.",
         "Bộ phận mua hàng lưu hồ sơ nhà cung cấp."]


def _header_table(page: int) -> DocElement:
    # The extractor splits the same header grid differently on some pages.
    if page % 2:
        return _t([["CÔNG TY ABC", "QUY TRÌNH MUA HÀNG", "Mã hiệu:", "QT-07"],
                   ["", "", "Lần ban hành:", "02"],
                   ["", "", "Ngày ban hành:", "01/02/2024"]], page)
    return _t([["Mã hiệu:", "QT-07"], ["Lần ban hành:", "02"], ["Ngày ban hành:", "01/02/2024"]],
              page)


def test_page_header_drawn_as_a_table_is_removed_and_body_tables_are_kept():
    elements = [_h("Quy trình mua hàng", 1)]
    for page in range(1, 6):
        elements += [_header_table(page), _p(_BODY[page - 1], page),
                     _t([["Bước", "Nội dung"], [str(page), _BODY[page - 1]]], page, 1)]
    result = clean_document(_pdf(elements, 5))
    md = render(result.document).markdown
    assert "Mã hiệu" not in md and "QT-07" not in md and "01/02/2024" not in md
    for text in _BODY:
        assert text in md
    body_tables = [el for el in result.document.elements if el.kind == "table"
                   and el.role == "content"]
    assert len(body_tables) == 5 and all(t.rows[0] == ["Bước", "Nội dung"] for t in body_tables)
    assert all(el.role == "header" for el in result.document.elements if el.kind == "table"
               and "Mã hiệu:" in str(el.rows))
    assert (result.meta.doc_code, result.meta.revision_label) == ("QT-07", "02")  # read from it


def test_label_value_header_spanning_many_elements_is_removed_whole():
    label_value = ["Chương trình phát triển", "SOP Title:", "Receiving Samples", "SOP Number:",
                   "40512", "Revision:", "03"]
    elements = []
    for page in range(1, 6):
        elements += [_p(text, page) for text in label_value]
        elements += [_h(f"{page}.0 Section {'abcde'[page - 1]}", page),
                     _p(f"Body of section {'abcde'[page - 1]} describes one step.", page)]
    per_page = len(label_value) + 2
    middle = 2 * per_page + len(label_value) + 1  # page 3, between its heading and its body
    elements.insert(middle, _p("SOP Number:", 3))  # a repeated text inside the body
    result = clean_document(_pdf(elements, 5))
    md = render(result.document).markdown
    for text in ("Chương trình phát triển", "SOP Title:", "Receiving Samples", "40512",
                 "Revision:"):
        assert text not in md
    assert md.count("SOP Number:") == 1  # the body occurrence is not at a page edge
    assert "Body of section c describes one step." in md and "3.0 Section c" in md


def test_numbered_headings_starting_each_page_are_not_one_repeated_line():
    elements = []
    for page in range(1, 6):
        elements += [_h(f"{page}.1 General", page), _p(f"Section {'abcde'[page - 1]} text.", page)]
    result = clean_document(_pdf(elements, 5))
    assert all(el.role == "content" for el in result.document.elements)


def test_national_motto_returned_as_the_first_heading_or_a_table_is_frame():
    heading_motto = _pdf([
        _h("BỘ ABC ___ CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc", 1),
        _p("Số: 12/QĐ-ABC", 1), _h("QUYẾT ĐỊNH Về việc ban hành quy chế", 1),
        _p("Điều 1. Ban hành kèm theo Quyết định này Quy chế làm việc.", 1)], 1)
    result = clean_document(heading_motto)
    md = render(result.document).markdown
    assert "CỘNG HÒA" not in md and "QUYẾT ĐỊNH Về việc ban hành quy chế" in md
    assert result.boilerplate[0].kind == "national_motto"

    table_motto = _pdf([
        _t([["BỘ ABC", "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc"],
            ["Số: 7/TB-ABC", "Hà Nội, ngày 3 tháng 4 năm 2025"]], 1),
        _h("THÔNG BÁO", 1), _p("Nội dung thông báo kết luận cuộc họp.", 1)], 1)
    md = render(clean_document(table_motto).document).markdown
    assert "CỘNG HOÀ" not in md and md.startswith("# THÔNG BÁO")


def test_recipients_label_returned_as_a_heading_is_frame():
    doc = _pdf([_h("THÔNG BÁO", 1), _p("Cơ quan đề nghị các đơn vị thực hiện./.", 1),
                _h("Nơi nhận:", 1), _p("Các Bộ;", 1, "list_item"), _p("Lưu: VT.", 1, "list_item"),
                _h("KT. BỘ TRƯỞNG THỨ TRƯỞNG", 1), _p("Nguyễn Văn B", 1)], 1)
    result = clean_document(doc)
    md = render(result.document).markdown
    assert md == "# THÔNG BÁO\n\nCơ quan đề nghị các đơn vị thực hiện./."
    kinds = [b.kind for b in result.boilerplate]
    assert kinds == ["recipients"] * 3 + ["signature"] * 2

    section = _pdf([_h("Distribution", 1), _p("Copies go to each laboratory.", 1),
                    _p("Controlled copies;", 1, "list_item")], 1)
    assert clean_document(section).boilerplate == []  # a heading needs the colon


def test_body_tables_with_role_or_issue_columns_are_kept_and_revision_history_is_frame():
    roles_per_type = _t([["TT", "Loại tài liệu", "Biên soạn", "Soát xét", "Phê duyệt"],
                         ["1", "Quy trình", "Phòng", "Ban ISO", "Giám đốc"],
                         ["2", "Biểu mẫu", "Phòng", "Ban ISO", "Trưởng phòng"]], 2, 1)
    register = _t([["STT", "Tên tài liệu", "Mã số", "Lần ban hành", "Ngày ban hành"],
                   ["1", "Sổ tay chất lượng", "ST-01", "02", "01/02/2024"]], 3, 1)
    history = _t([["History", "Effective Date"], ["Revision 4: updated step 2", "May 1, 2023"]],
                 3, 1)
    doc = _pdf([_h("Kiểm soát tài liệu", 1), _p("Quy định phân công.", 1), roles_per_type,
                _p("Danh mục tài liệu.", 3), register, _h("Revision History", 3), history], 3)
    result = clean_document(doc)
    md = render(result.document).markdown
    assert "Loại tài liệu" in md and "Tên tài liệu" in md
    assert "Effective Date" not in md and "Revision History" not in md
    assert {b.kind for b in result.boilerplate} == {"revision_table", "revision_table_title"}


def test_table_split_by_a_header_table_is_joined_after_cleaning_and_chunks_span_pages():
    head = ["TT", "Hoạt động", "Trách nhiệm", "Mô tả"]
    elements = []
    for page in range(1, 5):
        elements.append(_header_table(page))
        if page == 1:
            elements += [_h("Quy trình mua hàng", 1), _p("Mục đích: quy định việc mua hàng.", 1)]
        if page in (2, 3):  # one procedure table over pages 2-4; page 3 repeats its header
            rows = [[str(page), _BODY[page], "Phòng mua hàng", _BODY[page - 1]]]
            elements.append(_t(([head] if page == 3 else []) + rows, page,
                               1 if page == 3 else 0))
        if page == 4:
            elements.append(_t([["4", _BODY[4], "Kế toán", _BODY[3]]], page))
    elements.insert(4, _t([head, ["1", _BODY[0], "Nhân viên", _BODY[1]]], 1, 1))
    result = clean_document(_pdf(elements, 4))
    tables = [el for el in result.document.elements if el.role == "content" and el.kind == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert (table.page, table.page_end) == (1, 4)
    assert len(table.rows) == 5 and table.row_pages == [1, 1, 2, 3, 4]  # header row dropped once
    rendered = render(result.document)
    chunks = chunk_document(rendered, Words(), title="Quy trình", doc_code="QT-07",
                            config=ChunkConfig(min_tokens=1))
    steps = [c for c in chunks if c.kind == "PROCEDURE_STEP"]
    assert [(c.page_start, c.page_end) for c in steps] == [(1, 1), (2, 2), (3, 3), (4, 4)]

    # A plain (non-procedure) table: the chunk covering both parts spans both pages.
    plain = [_header_table(1), _h("Hồ sơ lưu", 1),
             _t([["Mã", "Tên hồ sơ", "Nơi lưu"], ["H1", "Phiếu đề nghị", "Phòng mua hàng"]], 1, 1),
             _header_table(2), _t([["H2", "Biên bản nhận hàng", "Kho"]], 2),
             _header_table(3), _p("Hồ sơ được lưu tối thiểu ba năm.", 3)]
    rendered = render(clean_document(_pdf(plain, 3)).document)
    chunks = chunk_document(rendered, Words(), title="Hồ sơ", doc_code="QT-07",
                            config=ChunkConfig(min_tokens=1))
    covering = [c for c in chunks if "Biên bản nhận hàng" in c.content]
    assert covering and all(c.page_start == 1 and c.page_end >= 2 for c in covering)


def test_next_page_table_with_its_own_header_is_not_joined():
    elements = [_t([["Mã", "Tên"], ["A1", "Hồ sơ một"]], 1, 1),
                _t([["Bước", "Người làm"], ["1", "Kế toán"]], 2, 1)]
    result = clean_document(_pdf(elements, 2))
    assert len([e for e in result.document.elements if e.kind == "table"]) == 2
