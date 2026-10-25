"""PDF adapter over Docling (ADR-008). The only module that imports the PDF library.

OCR is disabled, the converter loads models from ``SOPILOT_PDF_ARTIFACTS_PATH`` when set, and no
second library or fallback exists: a failure maps to a stable ``FailureCode``.
"""
from __future__ import annotations

import io
import os
from functools import lru_cache
from typing import Any

from sopilot_ai.docproc.errors import ExtractionError, FailureCode
from sopilot_ai.docproc.model import DocElement, StructuredDocument

# A PDF is "without a text layer" when fewer than this share of its pages has any character,
# or it has fewer than MIN_TOTAL_CHARS characters (TECH-V2-ai-service §5.2).
MIN_TEXT_PAGE_RATIO = 0.10
MIN_TOTAL_CHARS = 200
_BULLETS = {"-", "•", "*", "·", "●", "▪"}


def _precheck(data: bytes) -> int:
    """Open with pdfium to classify encrypted/corrupt/no-text-layer files; return page count."""
    import pypdfium2 as pdfium
    from pypdfium2._helpers.misc import PdfiumError

    try:
        pdf = pdfium.PdfDocument(data)
    except PdfiumError as exc:
        if "password" in str(exc).lower():
            raise ExtractionError(FailureCode.ENCRYPTED_PDF) from None
        raise ExtractionError(FailureCode.CORRUPT_FILE) from None
    try:
        count = len(pdf)
        if count == 0:
            raise ExtractionError(FailureCode.CORRUPT_FILE)
        counts = []
        for i in range(count):
            page = pdf[i]
            textpage = page.get_textpage()
            counts.append(textpage.count_chars())
            textpage.close()
            page.close()
    finally:
        pdf.close()
    with_text = sum(1 for c in counts if c > 0)
    if with_text / count < MIN_TEXT_PAGE_RATIO or sum(counts) < MIN_TOTAL_CHARS:
        raise ExtractionError(FailureCode.NO_TEXT_LAYER)
    return count


@lru_cache(maxsize=1)
def _converter() -> Any:
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        do_ocr=False,  # ADR-008: OCR stays off; image-only pages yield 0 characters.
        do_table_structure=True,
        artifacts_path=os.environ.get("SOPILOT_PDF_ARTIFACTS_PATH") or None,
        accelerator_options=AcceleratorOptions(
            num_threads=int(os.environ.get("SOPILOT_PDF_THREADS", "4")), device="cpu"
        ),
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )


def _pages(item: Any) -> tuple[int | None, int | None]:
    pages = [p.page_no for p in getattr(item, "prov", [])]
    return (min(pages), max(pages)) if pages else (None, None)


def _table_element(item: Any) -> DocElement | None:
    data = item.data
    rows_n, cols_n = data.num_rows, data.num_cols
    if rows_n == 0 or cols_n == 0:
        return None
    grid = [[""] * cols_n for _ in range(rows_n)]
    spans: list[tuple[int, int, int, int]] = []
    header_flags = [False] * rows_n
    for cell in data.table_cells:
        r, c = cell.start_row_offset_idx, cell.start_col_offset_idx
        if r < rows_n and c < cols_n:
            grid[r][c] = cell.text
            if cell.column_header:
                header_flags[r] = True
            if cell.row_span > 1 or cell.col_span > 1:
                spans.append((r, c, cell.row_span, cell.col_span))
    header_rows = 0
    while header_rows < rows_n and header_flags[header_rows]:
        header_rows += 1
    page, page_end = _pages(item)
    return DocElement(
        kind="table",
        rows=grid,
        header_rows=header_rows,
        cell_spans=spans,  # [] = the library reports no merged cells; None would mean unknown.
        page=page,
        page_end=page_end,
        row_pages=[page] * rows_n if page is not None else None,
    )


def _merge_tables(prev: DocElement, cur: DocElement) -> bool:
    """Join a continuation table on the next page (same width, repeated header row)."""
    assert prev.rows and cur.rows
    if prev.page_end is None or cur.page is None or cur.page != prev.page_end + 1:
        return False
    if len(prev.rows[0]) != len(cur.rows[0]):
        return False
    if [c.strip() for c in prev.rows[0]] != [c.strip() for c in cur.rows[0]]:
        return False
    offset = len(prev.rows)
    prev.rows.extend(cur.rows[1:])  # drop the repeated header row
    prev.row_pages = (prev.row_pages or []) + (cur.row_pages or [cur.page] * len(cur.rows))[1:]
    for r, c, rs, cs in cur.cell_spans or []:
        if r >= 1:
            prev.cell_spans = (prev.cell_spans or []) + [(r - 1 + offset, c, rs, cs)]
    prev.page_end = cur.page_end
    return True


def _vertical_key(item: Any) -> float:
    """Top-to-bottom sort key for an item on its first page (smaller = higher on the page)."""
    box = item.prov[0].bbox
    return -box.t if str(box.coord_origin).endswith("BOTTOMLEFT") else box.t


def _is_multi_column(items: list[Any]) -> bool:
    """True when two items on a page sit side by side (overlap vertically, not horizontally)."""
    boxes = [i.prov[0].bbox for i in items if i.prov]
    for a_i, a in enumerate(boxes):
        for b in boxes[a_i + 1:]:
            a_lo, a_hi = sorted((a.t, a.b))
            b_lo, b_hi = sorted((b.t, b.b))
            v_overlap = min(a_hi, b_hi) - max(a_lo, b_lo)
            h_overlap = min(a.r, b.r) - max(a.l, b.l)
            if v_overlap > 0 and h_overlap <= 0:
                return True
    return False


def _reading_order(items: list[Any]) -> list[Any]:
    """Docling groups non-adjacent list items into one group, which breaks reading order
    around tables and page breaks (observed, ADR-008 section 6). Re-sequence by page, and
    inside single-column pages by vertical position. Multi-column pages keep Docling's order."""
    by_page: dict[int, list[Any]] = {}
    current = 1
    for item in items:
        page = _pages(item)[0]
        current = page if page is not None else current
        by_page.setdefault(current, []).append(item)
    ordered: list[Any] = []
    for page in sorted(by_page):
        page_items = by_page[page]
        if all(i.prov for i in page_items) and not _is_multi_column(page_items):
            page_items = sorted(page_items, key=_vertical_key)
        ordered.extend(page_items)
    return ordered


def _convert(doc: Any) -> list[DocElement]:
    from docling_core.types.doc import (
        DocItemLabel,
        ListItem,
        SectionHeaderItem,
        TableItem,
        TextItem,
        TitleItem,
    )
    from docling_core.types.doc.document import ContentLayer

    elements: list[DocElement] = []
    last_content: DocElement | None = None
    iterated = [
        item for item, _ in doc.iterate_items(
            with_groups=False,
            included_content_layers={ContentLayer.BODY, ContentLayer.FURNITURE},
        )
    ]
    for item in _reading_order(iterated):
        page, page_end = _pages(item)
        furniture = getattr(item, "content_layer", ContentLayer.BODY) == ContentLayer.FURNITURE
        label = getattr(item, "label", None)
        role = "content"
        if label == DocItemLabel.PAGE_HEADER:
            role = "header"
        elif label == DocItemLabel.PAGE_FOOTER:
            role = "footer"
        elif furniture:
            role = "boilerplate"

        element: DocElement | None = None
        if isinstance(item, TableItem):
            element = _table_element(item)
            if element and role == "content":
                prev = last_content
                if prev and prev.kind == "table" and _merge_tables(prev, element):
                    continue
        elif isinstance(item, TitleItem):
            element = DocElement(kind="heading", level=1, text=item.text, page=page,
                                 page_end=page_end)
        elif isinstance(item, SectionHeaderItem):
            element = DocElement(kind="heading", level=max(1, min(item.level, 6)), text=item.text,
                                 page=page, page_end=page_end)
        elif isinstance(item, ListItem):
            marker = (item.marker or "").strip()
            element = DocElement(kind="list_item", text=item.text, level=1,
                                 number=marker if marker and marker not in _BULLETS else None,
                                 page=page, page_end=page_end)
        elif isinstance(item, TextItem):
            if label == DocItemLabel.CODE:
                element = DocElement(kind="code", text=item.text, page=page, page_end=page_end)
            elif item.text.strip():
                element = DocElement(kind="paragraph", text=item.text, page=page,
                                     page_end=page_end)
        if element is None:
            continue
        element.role = role  # type: ignore[assignment]
        elements.append(element)
        if role == "content":
            last_content = element
    return elements


def extract_pdf(data: bytes) -> StructuredDocument:
    page_count = _precheck(data)
    warnings: list[dict] = []
    try:
        from docling.datamodel.base_models import ConversionStatus, DocumentStream

        result = _converter().convert(
            DocumentStream(name="document.pdf", stream=io.BytesIO(data)), raises_on_error=False
        )
        if result.status in (ConversionStatus.FAILURE, ConversionStatus.SKIPPED):
            raise ExtractionError(FailureCode.EXTRACTION_ERROR)
        elements = _convert(result.document)
        if result.status == ConversionStatus.PARTIAL_SUCCESS:
            warnings.append({"kind": "PARTIAL_SUCCESS", "pages": []})
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError(FailureCode.EXTRACTION_ERROR) from None
    if not any(e.role == "content" and (e.text.strip() or e.rows) for e in elements):
        raise ExtractionError(FailureCode.NO_TEXT_LAYER)
    return StructuredDocument(file_type="PDF", elements=elements, page_count=page_count,
                              converter_warnings=warnings)
