"""V2-47 P4: repeated letterhead tables and decorative lines are frame (synthetic documents)."""
from __future__ import annotations

import itertools

from sopilot_ai.docproc import DocElement, StructuredDocument, render
from sopilot_ai.docproc.clean import clean_document


def _p(text: str, page: int, kind: str = "paragraph") -> DocElement:
    return DocElement(kind=kind, text=text, page=page)


def _h(text: str, page: int) -> DocElement:
    return DocElement(kind="heading", text=text, level=1, page=page)


def _t(rows: list[list[str]], page: int, header_rows: int = 0) -> DocElement:
    return DocElement(kind="table", rows=rows, page=page, header_rows=header_rows,
                      row_pages=[page] * len(rows))


def _pdf(elements: list[DocElement], pages: int) -> StructuredDocument:
    return StructuredDocument(file_type="PDF", elements=elements, page_count=pages)


def _letterhead(page: int) -> DocElement:
    return _t([["CẢNG VỤ THÁI", "QUY TRÌNH HỌP XEM XÉT CỦA LÃNH ĐẠO VỀ HỆ THỐNG QUẢN LÝ CHẤT LƯỢNG",
                "Mã hiệu:", "QT.05"],
               ["", "", "Lần ban hành", "01"],
               ["", "", "HÀNG HẢI Ngày ban hành:", "03/5/2021"]], page)


_serial = itertools.count(1)


def _word() -> str:
    """A letters-only token that never repeats (digits are masked by the repeat key)."""
    n = next(_serial)
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("a") + rem) + letters
    return letters


def _body(page: int, count: int = 2) -> list[DocElement]:
    return [_p(f"Bước {_word()} xử lý hồ sơ {_word()} {_word()}.", page) for _ in range(count)]


def _letterhead_doc(pages_with_table: list[int], pages: int = 11) -> StructuredDocument:
    elements: list[DocElement] = [_h("Quy trình họp xem xét", 1)]
    for page in range(1, pages + 1):
        if page in pages_with_table:
            elements.append(_letterhead(page))
        elements += _body(page)
    return _pdf(elements, pages)


def test_an_identical_letterhead_table_on_four_of_eleven_pages_is_header():
    result = clean_document(_letterhead_doc([5, 7, 8, 9]))
    md = render(result.document).markdown
    assert "Mã hiệu" not in md and "QT.05" not in md and "CẢNG VỤ" not in md
    tables = [el for el in result.document.elements if el.kind == "table"]
    assert len(tables) == 4 and all(el.role == "header" for el in tables)
    listed = [b for b in result.boilerplate if "Mã hiệu:" in b.text]
    assert sorted(b.page for b in listed) == [5, 7, 8, 9]
    assert all(el.text in md for el in result.document.elements if el.kind == "paragraph")


def test_a_step_table_whose_header_row_repeats_on_each_page_is_kept():
    head = ["TT", "Hoạt động", "Trách nhiệm", "Yêu cầu", "Biểu mẫu"]
    elements: list[DocElement] = [_h("Quy trình thực hiện", 1)]
    data: list[str] = []
    for page in range(1, 7):
        rows = [head] + [[str(2 * page + k), f"Thực hiện công việc {_word()}",
                          f"Phòng {_word()}", f"Đúng hạn {_word()}", f"BM.{_word()}"]
                         for k in range(2)]
        data += [row[1] for row in rows[1:]]
        elements += [_t(rows, page, header_rows=1), _p(f"Ghi chú cuối trang {_word()}.", page)]
    result = clean_document(_pdf(elements, 6))
    md = render(result.document).markdown
    assert all(text in md for text in data)
    assert "Hoạt động" in md
    assert all(el.role == "content" for el in result.document.elements)


def test_an_identical_small_table_on_two_pages_is_kept():
    elements: list[DocElement] = [_h("Quy trình", 1)]
    for page in range(1, 6):
        if page in (1, 2):
            elements.append(_letterhead(page))
        elements += _body(page)
    result = clean_document(_pdf(elements, 5))
    assert all(el.role == "content" for el in result.document.elements)
    assert "QT.05" in render(result.document).markdown


def test_an_identical_table_in_the_middle_of_a_page_is_kept():
    # Outside the edge window: 11 elements above and below it on each page.
    elements: list[DocElement] = [_h("Quy trình", 1)]
    for page in range(1, 6):
        elements += _body(page, 11) + [_letterhead(page)] + _body(page, 11)
    result = clean_document(_pdf(elements, 5))
    assert all(el.role == "content" for el in result.document.elements)

    # Inside the edge window but between body elements: the run from the edge stops first.
    elements = [_h("Quy trình", 1)]
    for page in range(1, 6):
        elements += _body(page, 2) + [_letterhead(page)] + _body(page, 2)
    result = clean_document(_pdf(elements, 5))
    assert all(el.role == "content" for el in result.document.elements)
    assert render(result.document).markdown.count("QT.05") == 5


def test_small_tables_that_differ_only_in_numbers_are_kept():
    values = {5: ("25 °C", "30 phút"), 6: ("40 °C", "15 phút"), 7: ("60 °C", "10 phút")}
    elements: list[DocElement] = [_h("Quy trình xử lý nhiệt", 1)]
    for page in range(1, 41):
        if page in values:
            temp, time = values[page]
            elements.append(_t([["Nhiệt độ", temp], ["Thời gian", time]], page))
        elements += _body(page)
    result = clean_document(_pdf(elements, 40))
    assert all(el.role == "content" for el in result.document.elements)
    md = render(result.document).markdown
    assert all(t in md for pair in values.values() for t in pair)


def test_the_line_ratio_is_unchanged():
    elements: list[DocElement] = [_h("Quy trình họp xem xét", 1)]
    for page in range(1, 12):
        if page in (5, 7, 8, 9):
            elements.append(_p("CẢNG VỤ THÁI", page))
        elements += _body(page)
    result = clean_document(_pdf(elements, 11))
    assert all(el.role == "content" for el in result.document.elements)
    assert render(result.document).markdown.count("CẢNG VỤ THÁI") == 4


def test_a_line_of_underscores_is_a_decorative_boilerplate_block():
    lines = ["_____________", "- - - - -", "==== ", "***", "~~~", "....."]
    elements = [_h("Quy trình", 1), _p("Nội dung mở đầu của quy trình.", 1)]
    for line in lines:
        elements += [_p(line, 1), _p(f"Đoạn văn sau {len(line)}.", 1)]
    result = clean_document(_pdf(elements, 1))
    md = render(result.document).markdown
    decorative = [b for b in result.boilerplate if b.kind == "decorative_line"]
    assert sorted(b.text for b in decorative) == sorted(line.strip() for line in lines)
    assert "___" not in md and "***" not in md and "~~~" not in md and "....." not in md
    assert "- - -" not in md and "====" not in md
    assert "Nội dung mở đầu của quy trình." in md and "Đoạn văn sau 13." in md


def test_lines_with_letters_digits_or_ellipsis_are_kept():
    kept = [_p("Nội dung: ........", 1), _p("- Không", 1), _p("1.", 1), _p("…", 1),
            _p("a | b", 1), _p("----", 1, "list_item"), _p("-", 1), _p(".", 1), _p("..", 1),
            _p("- -", 1)]
    elements = [_h("Quy trình", 1), *kept, _p("Đoạn cuối của tài liệu.", 1)]
    result = clean_document(_pdf(elements, 1))
    assert all(el.role == "content" for el in result.document.elements)
    assert not [b for b in result.boilerplate if b.kind == "decorative_line"]
    rows = DocElement(kind="table", rows=[["____", "____"], ["----", "===="]], page=1)
    result = clean_document(_pdf([_h("Quy trình", 1), rows, _p("Đoạn cuối.", 1)], 1))
    assert all(el.role == "content" for el in result.document.elements)
