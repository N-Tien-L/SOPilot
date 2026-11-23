"""Markdown states its structure, so no numbered line is promoted to a heading by pattern."""
from __future__ import annotations

from sopilot_ai.docproc import DocElement, StructuredDocument, chunk_document, render


class Words:
    """Whitespace tokenizer: deterministic and independent of any model download."""

    def count(self, text: str) -> int:
        return len(text.split())


BODY = " ".join(f"word{i}" for i in range(30)) + "."


def _shifts() -> list[DocElement]:
    return [
        DocElement(kind="heading", text="On-call coverage", level=2),
        DocElement(kind="paragraph", text=BODY),
        DocElement(kind="list_item", text="APAC 23:00 - 07:00", number="1."),
        DocElement(kind="list_item", text="EMEA 07:00 - 15:00", number="2."),
        DocElement(kind="list_item", text="AMER 15:00 - 23:00", number="3."),
        DocElement(kind="paragraph", text=BODY),
    ]


def _paths(file_type: str) -> list[list[str]]:
    rendered = render(StructuredDocument(file_type=file_type, elements=_shifts(), page_count=None))
    return [c.section_path for c in chunk_document(rendered, Words(), title="Doc")]


def test_all_caps_numbered_list_item_in_markdown_is_not_a_heading():
    assert _paths("MD") == [["On-call coverage"]]


def test_numbered_line_in_a_converted_pdf_is_still_promoted_to_a_heading():
    paths = _paths("PDF")
    assert paths != [["On-call coverage"]]
    assert any(part.startswith("1. APAC") for path in paths for part in path)


def test_numbered_paragraph_in_markdown_is_body_text_not_a_heading():
    rendered = render(StructuredDocument(file_type="MD", page_count=None, elements=[
        DocElement(kind="heading", text="Scope", level=1),
        DocElement(kind="paragraph", text="2. Procedure"),
        DocElement(kind="paragraph", text=BODY),
    ]))
    chunks = chunk_document(rendered, Words(), title="Doc")
    assert [c.section_path for c in chunks] == [["Scope"]]
    assert "2. Procedure" in chunks[0].content


def _caps_only(file_type: str):
    rendered = render(StructuredDocument(file_type=file_type, page_count=None, elements=[
        DocElement(kind="paragraph", text="WEEKLY STATUS"),
        DocElement(kind="paragraph", text=BODY),
    ]))
    return chunk_document(rendered, Words(), title="Doc")


def test_all_caps_line_in_markdown_without_headings_is_not_promoted():
    assert [c.section_path for c in _caps_only("MD")] == [[]]


def test_all_caps_line_in_a_pdf_without_headings_is_still_promoted():
    assert [c.section_path for c in _caps_only("PDF")] == [["WEEKLY STATUS"]]


def test_hash_headings_in_markdown_still_build_the_path():
    rendered = render(StructuredDocument(file_type="MD", page_count=None, elements=[
        DocElement(kind="heading", text="Policy", level=1),
        DocElement(kind="heading", text="Leave", level=2),
        DocElement(kind="paragraph", text=BODY),
    ]))
    assert chunk_document(rendered, Words(), title="Doc")[0].section_path == ["Policy", "Leave"]
