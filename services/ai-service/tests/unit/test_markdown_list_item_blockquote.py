"""A list item that opens with ``>`` keeps its text and its marker (V2-47).

CommonMark reads ``- >$5,000 needs approval`` as a list item holding a blockquote, but authors
write it for "greater than". The extractor used to emit an empty list item plus an orphan
paragraph without the ``>``, so the amount read as "exactly $5,000".
"""
from __future__ import annotations

from sopilot_ai.docproc import extract, render


def _elements(markdown: str):
    return [(e.kind, e.text, e.number) for e in extract(markdown.encode(), "x.md").elements]


def test_list_item_opening_with_greater_than_keeps_text_and_marker():
    assert _elements("- Up to $5,000 via Navan.\n- >$5,000 needs Zip.\n") == [
        ("list_item", "Up to $5,000 via Navan.", None),
        ("list_item", ">$5,000 needs Zip.", None),
    ]


def test_marker_spacing_of_the_source_is_kept():
    assert _elements("- > quoted note\n") == [("list_item", "> quoted note", None)]


def test_numbered_list_item_opening_with_greater_than():
    assert _elements("1. >$5,000 needs Zip.\n2. Next step.\n") == [
        ("list_item", ">$5,000 needs Zip.", "1."),
        ("list_item", "Next step.", "2."),
    ]


def test_rendered_markdown_reproduces_the_source_line():
    rendered = render(extract(b"- Up to $5,000 via Navan.\n- >$5,000 needs Zip.\n", "x.md"))
    assert "- >$5,000 needs Zip." in rendered.markdown
    assert "-\n" not in rendered.markdown.replace("- ", "-")  # no empty list item


def test_second_paragraph_of_the_quote_is_not_lost():
    elements = _elements("- > first\n  >\n  > second\n")
    assert elements[0] == ("list_item", "> first", None)
    assert ("paragraph", "second", None) in elements


def test_top_level_blockquote_and_plain_items_are_unchanged():
    assert _elements("> Note: be careful.\n\n- plain item\n") == [
        ("paragraph", "Note: be careful.", None),
        ("list_item", "plain item", None),
    ]
