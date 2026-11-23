from __future__ import annotations

from sopilot_ai.docproc.chunk.headings import Node, resolve_outline
from sopilot_ai.docproc.model import DocElement


def _with_offsets(elements: list[DocElement]) -> list[DocElement]:
    out, pos = [], 0
    for el in elements:
        text = el.text or ""
        out.append(el.model_copy(update={"char_start": pos, "char_end": pos + len(text)}))
        pos += len(text) + 2
    return out


def _p(text: str) -> DocElement:
    return DocElement(kind="paragraph", text=text)


def _h(text: str, level: int = 1) -> DocElement:
    return DocElement(kind="heading", text=text, level=level)


def _outline(elements: list[DocElement]) -> dict[str, Node]:
    return {n.el.text: n for n in resolve_outline(_with_offsets(elements))}


# A real heading elsewhere keeps the all-caps fallback out of these tests.
_ANCHOR = "Điều 1. Phạm vi điều chỉnh"


def test_a_numbered_line_ending_in_a_colon_is_body_not_a_heading():
    lines = [
        "2. Nghị định này bãi bỏ toàn bộ các Nghị định:",
        "3. Nghị định này bãi bỏ một phần các Nghị định:",
    ]
    nodes = _outline([_p(_ANCHOR), *[_p(t) for t in lines]])
    for text in lines:
        assert nodes[text].level is None


def test_a_depth_one_number_without_a_dot_is_not_a_heading():
    lines = [
        "1 Nghị định số 366/2025/NĐ-CP có căn cứ ban hành như sau:",
        "1 Phạm vi",
        "1 Nghị định số 366/2025/NĐ-CP có căn cứ ban hành như sau",
    ]
    nodes = _outline([_p(_ANCHOR), *[_p(t) for t in lines]])
    for text in lines:
        assert nodes[text].level is None


def test_numbered_headings_with_a_dot_or_parenthesis_still_resolve():
    elements = [
        _p("1. MỤC ĐÍCH"),
        _p("2) Phạm vi"),
        DocElement(kind="list_item", number="1.", text="MỤC mới"),
        _p("5.1 Trách nhiệm"),
    ]
    out = resolve_outline(_with_offsets(elements))
    assert [(n.level, n.kind) for n in out] == [
        (1, "numbered"), (1, "numbered"), (1, "numbered"), (2, "numbered"),
    ]


def test_articles_and_chapters_ending_in_a_colon_are_still_headings():
    nodes = _outline([_p("Điều 3: Hiệu lực"), _p("Chương II:")])
    assert nodes["Điều 3: Hiệu lực"].kind == "article"
    assert nodes["Chương II:"].kind == "chapter"


def test_a_converter_heading_ending_in_a_colon_keeps_its_level():
    nodes = _outline([_h("1. PHẠM VI:"), _p("Nội dung."), _h("DANH SÁCH PHÂN PHỐI TÀI LIỆU:")])
    for title in ("1. PHẠM VI:", "DANH SÁCH PHÂN PHỐI TÀI LIỆU:"):
        assert nodes[title].level == 1
        assert nodes[title].title == title
    lifted = _outline([_p("I. QUAN ĐIỂM"), _h("1. PHẠM VI:")])
    assert lifted["1. PHẠM VI:"].level == 2


def test_converter_sub_headings_ending_in_a_colon_keep_their_depth():
    elements = [_h("5. NỘI DUNG"), _h("5.1. Lưu đồ:"), _h("5.2 Diễn giải:"), _h("6. BIỂU MẪU")]
    out = resolve_outline(_with_offsets(elements))
    assert [(n.level, n.kind) for n in out[1:3]] == [(2, "numbered"), (2, "numbered")]
    assert out[0].level == 1 and out[3].level == 1


def test_a_numbered_list_item_sub_heading_ending_in_a_colon_is_still_a_heading():
    elements = [
        _h("5. NỘI DUNG"),
        DocElement(kind="list_item", number="5.1", text="Kiểm soát tài liệu:"),
        _h("5.1.1 Mục đích:"),
        _h("5.2 Kiểm soát hồ sơ:"),
    ]
    out = resolve_outline(_with_offsets(elements))
    assert [(n.level, n.kind) for n in out] == [
        (1, "numbered"), (2, "numbered"), (3, "numbered"), (2, "numbered"),
    ]


def test_roman_heading_still_resolves():
    nodes = _outline([_p("I. QUAN ĐIỂM")])
    assert (nodes["I. QUAN ĐIỂM"].level, nodes["I. QUAN ĐIỂM"].kind) == (1, "roman")
