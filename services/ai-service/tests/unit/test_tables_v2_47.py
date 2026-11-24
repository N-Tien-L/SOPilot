"""Step table continued on the next page: overflow stitching and one-column-narrower parts (V2-47).

Synthetic, Docling-free. The shapes mirror a procedure table whose last row overflows onto the
next page (the continuation part starts with a row of empty leading cells), where Docling also
drops a trailing column that is empty on that page and takes the overflow row for a header row.
TECH-V2-ai-service §5.2.
"""
from __future__ import annotations

from fakes import Words
from sopilot_ai.docproc import ChunkConfig, DocElement, StructuredDocument, chunk_document, render
from sopilot_ai.docproc.chunk.procedure_table import step_rows
from sopilot_ai.docproc.tables import append_continuation, join_continued_tables

HEAD = ["TT", "Hoạt động", "Trách nhiệm", "Yêu cầu", "Biểu mẫu"]
# Overflow text as a header-row lookalike: long, as real overflow is (a header cell is a label).
OVF4 = "OVF4 phần hai của yêu cầu, tiếp tục từ trang trước sang trang này"
OVF6 = "OVF6 phần hai của yêu cầu, tiếp tục từ trang trước sang trang này"


def _t(rows: list[list[str]], page: int, header_rows: int = 0, spans=None,
       role: str = "content") -> DocElement:
    return DocElement(kind="table", rows=rows, page=page, header_rows=header_rows,
                      row_pages=[page] * len(rows), cell_spans=spans, role=role)


def _frame(page: int) -> list[DocElement]:
    """Letterhead table and a line, already marked as frame (role preset)."""
    return [_t([["Mã hiệu:", "QT-05"], ["Lần ban hành:", "01"]], page, role="header"),
            DocElement(kind="paragraph", text="Trang", page=page, role="footer")]


def _doc(elements: list[DocElement]) -> StructuredDocument:
    return StructuredDocument(file_type="PDF", elements=elements, page_count=8)


def _body_tables(doc: StructuredDocument) -> list[DocElement]:
    return [e for e in doc.elements if e.kind == "table" and e.role == "content"]


def _step(n: int, name: str, text: str) -> list[str]:
    return [str(n), name, "Ban ISO", text, ""]


def _tb_qt05_parts() -> list[DocElement]:
    """The five parts of the step table, frame between them (pages 4 to 8)."""
    p4 = _t([HEAD, _step(1, "Xác định nội dung", "Cuộc họp định kỳ OVF1")], 4, 1)
    p5 = _t([["", "", "", "OVF1 phần hai", ""],
             _step(2, "Chuẩn bị nội dung", "Gửi thông báo")], 5)
    p6 = _t([["", "", "", "OVF2 phần hai", ""], _step(3, "Tiến hành họp", "Ghi biên bản"),
             _step(4, "Ghi nhận kết quả", "Tổng hợp ý kiến")], 6)
    # Docling dropped the empty last column and took the overflow row for a header row.
    p7 = _t([["", "", "", OVF4],
             ["5", "Kết luận cuộc họp", "Chủ trì cuộc họp", "Căn cứ kết quả"],
             ["6", "Theo dõi thực hiện", "Ban ISO", "Giao việc"]], 7, 1)
    p8 = _t([["", "", "", OVF6], ["7", "Đánh giá", "Ban ISO", "Đối chiếu"],
             ["8", "Lưu hồ sơ", "Ban ISO", "Lưu trữ"]], 8)
    return [p4, *_frame(5), p5, *_frame(6), p6, *_frame(7), p7, *_frame(8), p8]


def test_a_continuation_row_is_stitched_into_the_last_row():
    prev = _t([HEAD, _step(1, "Xác định nội dung", "Cuộc họp")], 4, 1)
    cur = _t([["", "", "", "phần hai", "BM.01"], _step(2, "Chuẩn bị", "Gửi thông báo")], 5)
    doc = _doc([prev, *_frame(5), cur])
    assert join_continued_tables(doc) == 1
    (table,) = _body_tables(doc)
    assert len(table.rows) == 3  # the overflow row was not added
    assert table.rows[1] == ["1", "Xác định nội dung", "Ban ISO", "Cuộc họp phần hai", "BM.01"]
    assert table.rows[2][0] == "2"
    assert table.row_pages == [4, 4, 5]  # the stitched row keeps its page
    assert (table.page, table.page_end) == (4, 5)


def test_the_tb_qt05_step_table_becomes_one_table_over_pages_4_to_8():
    doc = _doc(_tb_qt05_parts())
    assert join_continued_tables(doc) == 4
    (table,) = _body_tables(doc)
    assert (table.page, table.page_end) == (4, 8)
    assert len(table.rows) == 9 and table.header_rows == 1
    assert [r[0] for r in table.rows] == ["TT", "1", "2", "3", "4", "5", "6", "7", "8"]
    assert table.row_pages == [4, 4, 5, 6, 6, 7, 7, 8, 8]
    assert all(len(r) == 5 for r in table.rows)
    assert table.rows[4][3] == f"Tổng hợp ý kiến {OVF4}"
    assert table.rows[5][4] == ""  # the dropped column is padded back as an empty cell

    rendered = render(doc)
    el = next(e for e in rendered.elements if e.kind == "table" and e.role == "content")
    assert el.row_spans and len(el.row_spans) == len(el.rows)
    assert all(el.char_start <= a < b <= el.char_end for a, b in el.row_spans)
    assert [a for a, _ in el.row_spans] == sorted(a for a, _ in el.row_spans)


def test_every_step_chunk_has_the_real_column_names():
    doc = _doc([DocElement(kind="heading", text="Quy trình xem xét", level=1, page=4),
                *_tb_qt05_parts()])
    join_continued_tables(doc)
    chunks = chunk_document(render(doc), Words(), title="Quy trình xem xét", doc_code="QT-05",
                            config=ChunkConfig(min_tokens=1))
    steps = [c for c in chunks if c.kind == "PROCEDURE_STEP"]
    assert len(steps) == 8
    assert not any("Cột" in c.content for c in steps)
    first_pages = [4, 5, 6, 6, 7, 7, 8, 8]
    for n, (chunk, page) in enumerate(zip(steps, first_pages, strict=True), start=1):
        assert f"TT: {n}" in chunk.content and chunk.content.split("TT:")[1].lstrip().startswith(
            str(n))
        assert (chunk.page_start, chunk.page_end) == (page, page)
    assert "Trách nhiệm: Chủ trì cuộc họp" in steps[4].content
    assert OVF4 in steps[3].content and "OVF4" not in steps[4].content
    assert "OVF1 phần hai" in steps[0].content and OVF6 in steps[5].content


def test_append_continuation_without_stitch_appends_a_continuation_row_as_before():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    cur = _t([["", "", "", "phần hai", ""], _step(2, "Chuẩn bị", "Gửi")], 5)
    append_continuation(prev, cur, 0)  # the extractor's call: default, no stitching
    assert len(prev.rows) == 4
    assert prev.rows[1][3] == "Cuộc họp" and prev.rows[2] == ["", "", "", "phần hai", ""]
    assert prev.row_pages == [4, 4, 5, 5] and prev.page_end == 5


def test_a_narrower_continuation_with_a_spurious_header_is_joined_and_padded():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    cur = _t([["", "", "", OVF4], ["2", "Chuẩn bị", "Ban ISO", "Gửi"]], 5, 1,
             spans=[(1, 1, 1, 2)])
    doc = _doc([prev, *_frame(5), cur])
    assert join_continued_tables(doc) == 1
    (table,) = _body_tables(doc)
    assert [len(r) for r in table.rows] == [5, 5, 5]
    assert table.rows[1][3] == f"Cuộc họp {OVF4}"
    assert table.rows[2] == ["2", "Chuẩn bị", "Ban ISO", "Gửi", ""]
    assert table.row_pages == [4, 4, 5]
    assert table.cell_spans == [(2, 1, 1, 2)]  # column index unchanged, row shifted by 0 + 2 - 1


def test_a_next_page_row_with_an_empty_number_but_a_step_name_is_a_new_row():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    cur = _t([["", "Bước chưa đánh số", "Ban ISO", "Nội dung", ""],
              _step(3, "Tiếp theo", "Nội dung")], 5)
    doc = _doc([prev, *_frame(5), cur])
    assert join_continued_tables(doc) == 1  # same width, no header: joined as before
    (table,) = _body_tables(doc)
    assert len(table.rows) == 4
    assert table.rows[1][3] == "Cuộc họp"  # nothing appended to the previous step
    assert table.rows[2][1] == "Bước chưa đánh số"
    assert table.row_pages == [4, 4, 5, 5]


def test_a_narrower_next_page_table_without_a_continuation_row_is_not_joined():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    cur = _t([["5", "Kết luận", "Chủ trì", "Căn cứ"], ["6", "Theo dõi", "Ban ISO", "Giao"]], 5, 1)
    doc = _doc([prev, *_frame(5), cur])
    assert join_continued_tables(doc) == 0
    assert len(_body_tables(doc)) == 2


def test_a_table_two_columns_narrower_is_not_joined():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    cur = _t([["", "", "phần hai"], ["2", "Chuẩn bị", "Ban ISO"]], 5, 1)
    doc = _doc([prev, *_frame(5), cur])
    assert join_continued_tables(doc) == 0
    assert len(_body_tables(doc)) == 2


def test_a_same_width_table_with_its_own_header_row_stays_separate():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    cur = _t([["Mã", "Tên", "Nơi lưu", "Thời hạn", "Ghi chú"],
              ["H1", "Phiếu", "Kho", "3 năm", ""]], 5, 1)
    doc = _doc([prev, cur])
    assert join_continued_tables(doc) == 0


def test_a_next_page_cross_tab_with_blank_corner_cells_is_a_new_table():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    cur = _t([["", "", "Q1", "Q2", "Q3"], ["A", "Chỉ tiêu", "1", "2", "3"]], 5, 1)
    doc = _doc([prev, *_frame(5), cur])
    assert join_continued_tables(doc) == 0
    assert len(_body_tables(doc)) == 2
    assert doc.elements[0].rows[1][3] == "Cuộc họp"


def test_a_next_page_narrower_cross_tab_with_blank_corner_cells_is_a_new_table():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1)
    for header in (["", "", "Q1", "Q2"], ["", "", "", "Tổng kết cả năm"]):  # short labels
        cur = _t([header, ["A", "Chỉ tiêu", "1", "2"]], 5, 1)
        doc = _doc([prev.model_copy(deep=True), *_frame(5), cur])
        assert join_continued_tables(doc) == 0
        assert len(_body_tables(doc)) == 2


def test_a_cell_span_on_the_stitched_row_moves_to_the_next_row():
    prev = _t([HEAD, _step(1, "Xác định", "Cuộc họp")], 4, 1, spans=[(1, 2, 1, 1)])
    # The merged form value is written on the first row of its span only (the overflow row).
    cur = _t([["", "", "", "phần hai", "BM.01"], _step(2, "Chuẩn bị", "Gửi"),
              _step(3, "Họp", "Ghi")], 5,
             spans=[(0, 4, 3, 1),   # rowspan 3 starting on the stitched row, covers steps 2, 3
                    (0, 0, 1, 2),   # rowspan 1 on the stitched row: dropped
                    (1, 0, 2, 1)])  # a later row: shifted
    doc = _doc([prev, *_frame(5), cur])
    assert join_continued_tables(doc) == 1
    (table,) = _body_tables(doc)
    assert len(table.rows) == 4
    assert table.cell_spans == [(1, 2, 1, 1), (2, 4, 2, 1), (2, 0, 2, 1)]
    assert all(r < len(table.rows) and r + rs <= len(table.rows)
               for r, _, rs, _ in table.cell_spans)
    steps = {s.row: s.content for s in step_rows(table)}
    assert "phần hai" in steps[1] and "BM.01" not in steps[1]  # not covered by the span
    assert "Biểu mẫu: BM.01" in steps[2] and "Biểu mẫu: BM.01" in steps[3]
