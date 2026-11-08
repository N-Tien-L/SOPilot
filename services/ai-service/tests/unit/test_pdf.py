"""PDF adapter tests on synthetic fixtures. They need the optional ``pdf`` extra (Docling) and,
on first run, the model artifacts (set ``SOPILOT_PDF_ARTIFACTS_PATH`` to run fully offline)."""
from __future__ import annotations

import sys
import unicodedata

import pytest

from sopilot_ai.docproc import ExtractionError, FailureCode, extract, render

pytest.importorskip("docling")
import pdf_fixtures  # noqa: E402

pytestmark = pytest.mark.pdf


@pytest.fixture(scope="module")
def english():
    doc = extract(pdf_fixtures.english_procedure(), "p.pdf")
    return doc, render(doc)


def test_pages_headings_and_table_position(english):
    doc, rendered = english
    assert doc.file_type == "PDF" and doc.page_count == 2
    content = [e for e in doc.elements if e.role == "content"]
    assert content[0].kind == "heading" and content[0].page == 1
    assert [e.page for e in content] == sorted(e.page for e in content)  # reading order by page
    md = rendered.markdown
    # Docling reads "2. Procedure" as a list item, not a heading: numbering-based heading
    # detection is V2-22's job. The table must still sit between it and the next section.
    assert md.index("Procedure") < md.index("| Step |") < md.index("3. Records") < md.index(
        "Records are kept")
    table = next(e for e in doc.elements if e.kind == "table")
    assert len(table.rows) == 3 and len(table.rows[0]) == 4
    assert table.cell_spans == []  # library reports no merged cells for this fixture


def test_every_element_offset_matches_and_pages_are_valid(english):
    doc, rendered = english
    for el in rendered.elements:
        if el.role == "content":
            assert rendered.markdown[el.char_start:el.char_end]
            assert 1 <= el.page <= doc.page_count
    assert [s.page for s in rendered.page_index] == [1, 2]
    assert rendered.page_index[0].char_end == rendered.page_index[1].char_start


def test_table_continued_on_next_page_is_one_element_with_row_pages():
    doc = extract(pdf_fixtures.continued_table(), "t.pdf")
    tables = [e for e in doc.elements if e.kind == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert (table.page, table.page_end) == (1, 2)
    assert len(table.rows) == 7  # one header + 6 task rows, repeated header dropped
    assert table.row_pages == [1, 1, 1, 1, 2, 2, 2]
    rendered = render(doc)
    assert [s.page for s in rendered.page_index] == [1, 2]
    second_page_start = rendered.page_index[1].char_start
    row_start = next(el for el in rendered.elements if el.kind == "table").row_spans[4][0]
    assert second_page_start == row_start  # page boundary falls on a row boundary


def test_vietnamese_is_nfc_and_keeps_diacritics_and_numbering():
    font = pdf_fixtures.find_font()
    if font is None:
        pytest.skip("no TrueType font with Vietnamese glyphs available")
    doc = extract(pdf_fixtures.vietnamese_procedure(font), "vi.pdf")
    md = render(doc).markdown
    assert unicodedata.is_normalized("NFC", md)
    for expected in ("Mục đích", "Phạm vi áp dụng", "Đối tượng", "Trưởng phòng phê duyệt"):
        assert expected in md
    assert md.index("Mục đích") < md.index("Phạm vi áp dụng") < md.index("Đối tượng")
    assert "a) Đơn hàng dưới 50 triệu" in md and "b) Đơn hàng từ 50 triệu" in md


def test_image_only_page_yields_zero_characters_and_no_ocr_engine_runs():
    doc = extract(pdf_fixtures.text_page_then_image_page(), "mixed.pdf")
    pages = {e.page for e in doc.elements if e.role == "content"}
    assert pages == {1}  # page 2 is a picture: nothing read from it
    text = render(doc).markdown
    assert "SCANNED" not in text
    ocr_modules = ("rapidocr", "easyocr", "tesserocr", "pytesseract", "ocrmac")
    assert not any(m in sys.modules for m in ocr_modules)
    from sopilot_ai.docproc.extract.pdf import _converter

    options = _converter().format_to_options[next(iter(_converter().format_to_options))]
    assert options.pipeline_options.do_ocr is False


def test_pdf_without_text_layer_is_rejected():
    with pytest.raises(ExtractionError) as exc:
        extract(pdf_fixtures.image_only(), "scan.pdf")
    assert exc.value.code is FailureCode.NO_TEXT_LAYER


def test_encrypted_pdf_is_rejected():
    with pytest.raises(ExtractionError) as exc:
        extract(pdf_fixtures.encrypted(), "locked.pdf")
    assert exc.value.code is FailureCode.ENCRYPTED_PDF


@pytest.mark.parametrize("data", [b"", b"%PDF-1.4\nnot really a pdf", b"plain text"])
def test_corrupt_pdf_is_rejected(data):
    with pytest.raises(ExtractionError) as exc:
        extract(data, "broken.pdf")
    assert exc.value.code is FailureCode.CORRUPT_FILE


def test_repeated_page_frame_is_cleaned_and_a_numbered_title_still_chunks_under_it():
    from sopilot_ai.docproc import ChunkConfig, chunk_document, clean_document

    class Words:
        def count(self, text: str) -> int:
            return len(text.split())

    doc = extract(pdf_fixtures.framed_procedure(), "framed.pdf")
    result = clean_document(doc)
    rendered = render(result.document)
    assert "ACME Corp" not in rendered.markdown and "Page 2 of 4" not in rendered.markdown
    assert "Body text of the charlie section" in rendered.markdown
    assert {b.kind for b in result.boilerplate} <= {"header", "footer", "boilerplate"}
    assert "BOILERPLATE_REMOVED" in [w.code for w in result.warnings]
    assert result.meta.doc_code == "QT-MH-01" and result.meta.revision_label == "2"
    merged = chunk_document(rendered, Words(), title="Procedure", doc_code="QT-MH-01")
    assert len(merged) == 1 and (merged[0].page_start, merged[0].page_end) == (1, 4)
    chunks = chunk_document(rendered, Words(), title="Procedure", doc_code=result.meta.doc_code,
                            config=ChunkConfig(min_tokens=1))
    assert any(c.section_path == ["3. Section charlie"] and c.page_start == 3 for c in chunks)
    for c in chunks:
        assert rendered.markdown[c.char_start:c.char_end] == c.content
