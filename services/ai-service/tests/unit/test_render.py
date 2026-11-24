from __future__ import annotations

import unicodedata

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sopilot_ai.docproc import DocElement, StructuredDocument, render
from sopilot_ai.docproc.render import NORMALIZER_VERSION, utf16_offset

_PROPERTY = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zl", "Zp"), max_codepoint=0x1FFFF),
    min_size=1,
    max_size=30,
).map(lambda s: unicodedata.normalize("NFC", s).strip() or "x")


@st.composite
def _element(draw, page: int):
    kind = draw(st.sampled_from(["heading", "paragraph", "list_item", "table", "code"]))
    if kind == "table":
        width = draw(st.integers(1, 4))
        n_rows = draw(st.integers(1, 5))
        rows = [[draw(_text) for _ in range(width)] for _ in range(n_rows)]
        row_pages = sorted(draw(st.integers(page, page + 1)) for _ in range(n_rows))
        return DocElement(kind="table", rows=rows, page=row_pages[0], page_end=row_pages[-1],
                          row_pages=row_pages)
    return DocElement(kind=kind, text=draw(_text), level=draw(st.integers(1, 3)), page=page,
                      number=draw(st.sampled_from([None, "5.1", "a)"])) if kind == "list_item"
                      else None)


@st.composite
def _document(draw):
    page = 1
    elements = []
    for _ in range(draw(st.integers(1, 8))):
        element = draw(_element(page))
        elements.append(element)
        page = element.page_end or page
        page += draw(st.integers(0, 1))
    return StructuredDocument(file_type="PDF", elements=elements, page_count=page + 1)


@_PROPERTY
@given(_document())
def test_offsets_match_the_rendered_block(doc):
    rendered = render(doc)
    previous_end = -2
    for el in rendered.elements:
        assert el.char_start is not None and el.char_end is not None
        assert el.char_start >= previous_end + 2 or previous_end == -2
        previous_end = el.char_end
        block = rendered.markdown[el.char_start:el.char_end]
        assert block and block == block.strip("\n")
        if el.kind == "table":
            assert el.row_spans and len(el.row_spans) == len(el.rows)
            last = el.char_start
            for start, end in el.row_spans:
                assert last <= start < end <= el.char_end
                line = rendered.markdown[start:end]
                assert line.startswith("|") and line.endswith("|") and "\n" not in line
                last = end


@_PROPERTY
@given(_document())
def test_page_index_is_contiguous_and_increasing(doc):
    rendered = render(doc)
    spans = rendered.page_index
    assert spans
    assert spans[-1].char_end == len(rendered.markdown)
    for a, b in zip(spans, spans[1:], strict=False):
        assert a.char_end == b.char_start
        assert a.page < b.page
        assert a.char_start < a.char_end


@_PROPERTY
@given(_document())
def test_render_is_deterministic(doc):
    assert render(doc) == render(doc)
    assert render(doc).normalizer_version == NORMALIZER_VERSION


def test_non_content_roles_are_not_rendered_and_have_no_offsets():
    doc = StructuredDocument(file_type="PDF", page_count=1, elements=[
        DocElement(kind="paragraph", text="Header line", page=1, role="header"),
        DocElement(kind="heading", text="Title", level=1, page=1),
        DocElement(kind="paragraph", text="Footer 1", page=1, role="footer"),
    ])
    rendered = render(doc)
    assert rendered.markdown == "# Title"
    assert [e.char_start for e in rendered.elements] == [None, 0, None]


def test_table_renders_gfm_with_one_row_span_each_and_escapes_pipes():
    rows = [["Step", "Owner"], ["1", "Staff | HR"], ["", "Manager"]]
    el = DocElement(kind="table", rows=rows, cell_spans=[(1, 0, 2, 1)])
    out = render(StructuredDocument(file_type="MD", elements=[el])).elements[0]
    md = render(StructuredDocument(file_type="MD", elements=[el])).markdown
    assert md.splitlines()[1] == "| --- | --- |"
    assert "Staff \\| HR" in md
    assert len(out.row_spans) == 3
    assert md[slice(*out.row_spans[2])] == "|  | Manager |"


def test_list_item_keeps_source_numbering():
    doc = StructuredDocument(file_type="MD", elements=[
        DocElement(kind="list_item", text="Prepare", number="5.1", level=1),
        DocElement(kind="list_item", text="Review", number="a)", level=2),
        DocElement(kind="list_item", text="Plain"),
    ])
    assert render(doc).markdown == "5.1 Prepare\n\n  a) Review\n\n- Plain"


def test_code_fence_outgrows_backticks_inside_code():
    doc = StructuredDocument(file_type="MD", elements=[
        DocElement(kind="code", text="a ``` b")])
    assert render(doc).markdown.startswith("````\n")


def test_utf16_offsets_count_astral_characters_as_two_units():
    text = "ab\U0001f600cd"
    assert utf16_offset(text, 3) == 4
    assert utf16_offset(text, len(text)) == 6
    doc = StructuredDocument(file_type="MD", elements=[
        DocElement(kind="paragraph", text="x\U0001f600y"), DocElement(kind="paragraph", text="z")])
    rendered = render(doc)
    second = rendered.elements[1]
    assert utf16_offset(rendered.markdown, second.char_start) == second.char_start + 1
