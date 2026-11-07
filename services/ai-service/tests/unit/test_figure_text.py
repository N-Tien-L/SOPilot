"""Text-layer words inside picture regions become ``figure_text`` elements (ADR-008 section 6.2).

These tests use fake Docling picture items over a real PDF opened with pdfium, so they do not
depend on the layout model deciding that a drawing is a picture."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("docling")
import pypdfium2 as pdfium  # noqa: E402
from docling_core.types.doc import BoundingBox, CoordOrigin  # noqa: E402

import pdf_fixtures  # noqa: E402
from sopilot_ai.docproc import DocElement, StructuredDocument, render  # noqa: E402
from sopilot_ai.docproc.extract.pdf import (  # noqa: E402
    _add_text,
    _exported_text,
    _normalized,
    _picture_element,
)

pytestmark = pytest.mark.pdf

FLOWCHART = (50, 340, 545, 500)  # left, bottom, right, top (PDF points)


@pytest.fixture(scope="module")
def pdf():
    document = pdfium.PdfDocument(pdf_fixtures.figure_page())
    yield document
    document.close()


def _picture(box, page=1):
    left, bottom, right, top = box
    bbox = BoundingBox(l=left, b=bottom, r=right, t=top, coord_origin=CoordOrigin.BOTTOMLEFT)
    return SimpleNamespace(prov=[SimpleNamespace(page_no=page, bbox=bbox)])


def _exported(*texts):
    elements = [DocElement(kind="paragraph", text=t, page=1) for t in texts]
    return _exported_text(elements)


def test_flowchart_lines_become_one_figure_text_element_in_order(pdf):
    page_text, page_items = _exported("Body paragraph the converter already exports.")
    el = _picture_element(_picture(FLOWCHART), pdf, page_text, page_items)
    assert el is not None and el.role == "figure_text" and el.kind == "paragraph"
    assert el.text.split("\n") == [
        "Review the request", "Approve or reject", "Archive the record", "YES"]
    assert (el.page, el.page_end) == (1, 1)


def test_words_outside_the_picture_box_are_not_taken(pdf):
    page_text, page_items = _exported()
    el = _picture_element(_picture((50, 420, 545, 500)), pdf, page_text, page_items)
    assert el is not None
    assert "Body paragraph" not in el.text and "Archive" not in el.text


def test_lines_docling_already_exported_are_not_repeated(pdf):
    page_text, page_items = _exported("Approve or reject", "YES")  # paragraph and a table cell
    el = _picture_element(_picture(FLOWCHART), pdf, page_text, page_items)
    assert el is not None
    assert el.text.split("\n") == ["Review the request", "Archive the record"]


def test_line_inside_a_longer_exported_paragraph_counts_as_duplicate(pdf):
    page_text, page_items = _exported("First Review the request then approve or reject it")
    el = _picture_element(_picture(FLOWCHART), pdf, page_text, page_items)
    assert el is not None
    assert "Review the request" not in el.text and "Archive the record" in el.text


def test_everything_already_exported_gives_no_element(pdf):
    page_text, page_items = _exported(
        "Review the request", "Approve or reject", "Archive the record", "YES")
    assert _picture_element(_picture(FLOWCHART), pdf, page_text, page_items) is None


def test_second_picture_with_the_same_words_is_a_duplicate(pdf):
    page_text, page_items = _exported()
    first = _picture_element(_picture(FLOWCHART), pdf, page_text, page_items)
    assert first is not None
    _add_text(page_text, page_items, first)
    assert _picture_element(_picture(FLOWCHART), pdf, page_text, page_items) is None


def test_fewer_than_two_words_is_dropped(pdf):
    page_text, page_items = _exported()
    assert _picture_element(_picture((50, 350, 545, 375)), pdf, page_text, page_items) is None


def test_frame_text_in_the_top_or_bottom_zone_keeps_header_footer_role(pdf):
    page_text, page_items = _exported()
    header = _picture_element(_picture((50, 795, 545, 830)), pdf, page_text, page_items)
    footer = _picture_element(_picture((50, 15, 545, 50)), pdf, page_text, page_items)
    assert header is not None and header.role == "header"
    assert header.text == "ACME PORT AUTHORITY"
    assert footer is not None and footer.role == "footer"
    assert footer.text == "Form QT-03 revision one"


def test_picture_without_page_or_outside_the_document_is_ignored(pdf):
    page_text, page_items = _exported()
    assert _picture_element(_picture(FLOWCHART, page=9), pdf, page_text, page_items) is None


def test_normalization_is_nfc_and_case_insensitive():
    assert _normalized("Hu\u1ebf  \u0110\u00c0") == _normalized("Hu\u00ea\u0301 \u0111a\u0300")


def test_figure_text_is_rendered_with_valid_offsets_and_header_is_not():
    doc = StructuredDocument(file_type="PDF", page_count=1, elements=[
        DocElement(kind="paragraph", text="Intro text", page=1),
        DocElement(kind="paragraph", text="Step one\nStep two", page=1, role="figure_text"),
        DocElement(kind="paragraph", text="ACME PORT AUTHORITY", page=1, role="header"),
    ])
    rendered = render(doc)
    figure = rendered.elements[1]
    assert rendered.markdown[figure.char_start:figure.char_end] == "Step one\nStep two"
    assert "ACME" not in rendered.markdown
    assert rendered.elements[2].char_start is None
