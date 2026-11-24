from __future__ import annotations

from sopilot_eval.chunk_invariants import check_chunks, continuation_blockers

HEADING = "# 1. Quy trình"
HEADER_ROW = "| Bước | Trách nhiệm |"
SEP = "| --- | --- |"
ROW1 = "| 1 | Nhân viên |"
ROW2 = "| 2 | Quản lý |"
TABLE = f"{HEADER_ROW}\n{SEP}\n{ROW1}\n{ROW2}"
MD = HEADING + "\n\n" + TABLE
T0 = len(HEADING) + 2
R0 = (T0, T0 + len(HEADER_ROW))
R1 = (R0[1] + 1 + len(SEP) + 1, R0[1] + 1 + len(SEP) + 1 + len(ROW1))
R2 = (R1[1] + 1, R1[1] + 1 + len(ROW2))

ELEMENTS = [
    {"kind": "heading", "char_start": 0, "char_end": len(HEADING), "page": 1, "page_end": 1},
    {"kind": "table", "char_start": T0, "char_end": len(MD), "page": 1, "page_end": 2,
     "row_spans": [R0, R1, R2], "row_pages": [1, 1, 2]},
]


def _chunk(kind, start, end, content=None, page=1, page_end=1, tokens=5):
    return {"kind": kind, "char_start": start, "char_end": end,
            "content": MD[start:end] if content is None else content,
            "page_start": page, "page_end": page_end, "token_count": tokens}


def test_well_formed_chunks_have_no_violations():
    chunks = [
        _chunk("TEXT", 0, len(HEADING)),
        _chunk("PROCEDURE_STEP", *R1, content="Bước: 1 | Trách nhiệm: Nhân viên"),
        _chunk("PROCEDURE_STEP", *R2, content="Bước: 2 | Trách nhiệm: Quản lý", page=2,
               page_end=2),
        # a row-cut table part: header repeated, offsets from first to last row of the part
        _chunk("TABLE", R1[0], R2[1], content=HEADER_ROW + "\n" + SEP + "\n" + MD[R1[0]:R2[1]],
               page=1, page_end=2),
        _chunk("TEXT", 0, len(MD), page=1, page_end=2),
    ]
    report = check_chunks(MD, ELEMENTS, chunks, max_tokens=10)
    assert sum(report["violations"].values()) == 0, report["examples"]
    assert report["multi_page_table_chunks"] == 2
    assert report["checked"]["procedure_row"] == 2


def test_each_broken_invariant_is_counted_with_an_example():
    chunks = [
        _chunk("TEXT", 0, len(HEADING), content="# 1. Quy trinh"),  # substring
        _chunk("PROCEDURE_STEP", *R2, content="x", page=1, page_end=1),  # row page is 2
        _chunk("TEXT", 0, len(HEADING), page=2, page_end=1),  # order and source page
        _chunk("TABLE", R1[0], R2[1], page=1, page_end=1),  # multi-page table, page_end 1
        _chunk("TEXT", 0, len(MD) + 5),  # offsets
        _chunk("TEXT", 0, len(HEADING), tokens=99),  # budget
    ]
    report = check_chunks(MD, ELEMENTS, chunks, max_tokens=10, doc_id="d")
    v = report["violations"]
    assert v["substring"] == 1
    assert v["procedure_row"] == 1
    assert v["page_order"] == 1
    assert v["page_source"] == 2  # chunk 2 (page 2 for a page-1 heading) and chunk 3
    assert v["multi_page_table"] == 1
    assert v["offsets"] == 1
    assert v["token_budget"] == 1
    assert {e["doc_id"] for e in report["examples"]} == {"d"}


def test_procedure_offsets_must_be_a_row_span():
    report = check_chunks(MD, ELEMENTS, [_chunk("PROCEDURE_STEP", R1[0], R2[1], content="x")])
    assert report["violations"]["procedure_row"] == 1


def test_continuation_blockers_name_the_failed_merge_condition():
    def table(page, header, role="content"):
        return {"kind": "table", "role": role, "page": page, "rows": [header, ["x"] * len(header)]}

    para = {"kind": "paragraph", "role": "content", "page": 3, "text": "p"}
    elements = [table(1, ["A", "B"]), table(2, ["SỞ", "QUY TRÌNH", "Mã hiệu"]),
                table(2, ["A", "B"]), table(3, ["A", "B"]), table(3, ["A", "B"]), para,
                table(4, ["C", "D"]), table(5, ["C", "D"], role="header"), table(5, ["E", "F"])]
    reasons = continuation_blockers(elements)
    assert reasons == {"width_differs": 1,  # page 1 -> page-header table on page 2
                       "would_merge": 1,  # page 2 -> 3
                       "body_text_after_table": 1,  # page 3 ends with a paragraph
                       "header_row_not_repeated": 1}  # page 4 -> 5 (header role is skipped)


def test_unpaged_markdown_chunks_need_null_pages():
    elements = [{"kind": "heading", "char_start": 0, "char_end": len(HEADING), "page": None}]
    ok = check_chunks(HEADING, elements, [_chunk("TEXT", 0, len(HEADING), page=None,
                                                  page_end=None)])
    bad = check_chunks(HEADING, elements, [_chunk("TEXT", 0, len(HEADING))])
    assert sum(ok["violations"].values()) == 0
    assert bad["violations"]["page_source"] == 1
