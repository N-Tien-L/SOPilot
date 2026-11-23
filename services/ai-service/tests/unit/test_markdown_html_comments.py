"""HTML comments in Markdown are not content (V2-47).

Handbook pages open and close with linter directives such as ``<!-- markdownlint-disable -->``.
They used to become a paragraph of their own: a 15-token first chunk with no section path.
"""
from __future__ import annotations

from sopilot_ai.docproc import chunk_document, extract, render


class Words:
    def count(self, text: str) -> int:
        return len(text.split())


def _elements(markdown: str):
    return [(e.kind, e.text) for e in extract(markdown.encode(), "x.md").elements]


def test_comment_only_block_is_not_an_element():
    assert _elements("<!-- markdownlint-disable MD051 -->\n\n# Title\n\nBody text.\n") == [
        ("heading", "Title"),
        ("paragraph", "Body text."),
    ]


def test_multiline_comment_block_is_dropped():
    assert _elements("<!--\nnote for editors\n-->\n\nBody text.\n") == [("paragraph", "Body text.")]


def test_comment_inside_a_paragraph_is_removed_and_text_kept():
    [(kind, text)] = _elements("Before <!-- hidden --> after.\n")
    assert kind == "paragraph" and text.split() == ["Before", "after."]


def test_other_html_block_is_kept_without_its_comment():
    elements = _elements("<div><!-- x -->kept</div>\n")
    assert elements == [("paragraph", "<div>kept</div>")]


def test_first_chunk_is_not_the_comment():
    body = " ".join(f"word{i}" for i in range(40)) + "."
    rendered = render(extract(f"<!-- markdownlint-disable -->\n\n# Title\n\n{body}\n\n"
                              "<!-- markdownlint-enable -->\n".encode(), "x.md"))
    chunks = chunk_document(rendered, Words(), title="Doc")
    assert all("markdownlint" not in c.content for c in chunks)
    assert chunks[0].section_path == ["Title"]
