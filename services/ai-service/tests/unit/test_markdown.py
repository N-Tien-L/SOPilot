from __future__ import annotations

import unicodedata

import pytest

from sopilot_ai.docproc import ExtractionError, FailureCode, extract, render

SAMPLE = """---
title: Nghỉ phép
tags: [hr]
---
# Chính sách nghỉ phép

Nhân viên được nghỉ phép theo quy định.
Dòng này nối với dòng trên. {{< note >}}Ẩn{{< /note >}}

1. Gửi đề nghị
2. Chờ phê duyệt
   - Quản lý trực tiếp
   - Nhân sự

<div class="x">raw html</div>

| Bước | Người thực hiện |
|---|---|
| 1 | Nhân viên |
| 2 | Quản lý |
"""


def _doc(text: str = SAMPLE):
    return extract(text.encode("utf-8"), "policy.md")


def test_frontmatter_is_stored_and_removed_from_content():
    doc = _doc()
    assert doc.frontmatter == {"title": "Nghỉ phép", "tags": ["hr"]}
    assert "title:" not in render(doc).markdown
    assert doc.file_type == "MD" and doc.page_count is None


def test_hugo_shortcodes_are_removed_and_lines_are_joined():
    md = render(_doc()).markdown
    assert "{{" not in md and "}}" not in md
    assert "Nhân viên được nghỉ phép theo quy định. Dòng này nối với dòng trên." in md


def test_headings_lists_tables_and_html_are_kept():
    doc = _doc()
    kinds = [e.kind for e in doc.elements]
    assert kinds[0] == "heading" and doc.elements[0].level == 1
    items = [e for e in doc.elements if e.kind == "list_item"]
    assert [i.number for i in items[:2]] == ["1.", "2."]
    assert [i.level for i in items] == [1, 1, 2, 2]
    table = next(e for e in doc.elements if e.kind == "table")
    assert table.rows == [["Bước", "Người thực hiện"], ["1", "Nhân viên"], ["2", "Quản lý"]]
    assert any(e.kind == "paragraph" and "raw html" in e.text for e in doc.elements)


def test_output_is_nfc_even_for_decomposed_input():
    decomposed = unicodedata.normalize("NFD", "# Quy trình mua hàng\n\nNgười đề nghị")
    md = render(extract(decomposed.encode(), "a.md")).markdown
    assert md == unicodedata.normalize("NFC", "# Quy trình mua hàng\n\nNgười đề nghị")


def test_english_text_round_trips():
    md = render(extract(b"# Leave policy\n\nEmployees accrue leave monthly.\n", "a.md")).markdown
    assert md == "# Leave policy\n\nEmployees accrue leave monthly."


def test_render_twice_gives_identical_output():
    assert render(_doc()).markdown == render(_doc()).markdown


def test_offsets_hold_for_every_element():
    rendered = render(_doc())
    for el in rendered.elements:
        assert rendered.markdown[el.char_start:el.char_end]


@pytest.mark.parametrize("data", [b"\xff\xfe\x00bad", "Nhân viên".encode("cp1258")])
def test_non_utf8_is_rejected(data):
    with pytest.raises(ExtractionError) as exc:
        extract(data, "a.md")
    assert exc.value.code is FailureCode.INVALID_ENCODING


def test_utf8_bom_is_accepted():
    assert extract(b"\xef\xbb\xbf# Title\n", "a.md").elements[0].text == "Title"


def test_astral_characters_keep_correct_offsets():
    rendered = render(extract("para \U0001f600\n\nsecond".encode(), "a.md"))
    second = rendered.elements[1]
    assert rendered.markdown[second.char_start:second.char_end] == "second"
