"""A heading with no body and no sub-section (a short numbered step) keeps its text in a chunk."""
from __future__ import annotations

import pytest

from sopilot_ai.docproc import (
    ChunkConfig,
    DocElement,
    DocFamily,
    ExtractionError,
    StructuredDocument,
    chunk_document,
    render,
)
from sopilot_ai.docproc.errors import FailureCode


class Words:
    """Whitespace tokenizer: deterministic and independent of any model download."""

    def count(self, text: str) -> int:
        return len(text.split())


def _h(text: str, level: int) -> DocElement:
    return DocElement(kind="heading", text=text, level=level)


def _p(text: str) -> DocElement:
    return DocElement(kind="paragraph", text=text)


BODY = " ".join(f"từ{i}" for i in range(30)) + "."


def _chunks(elements, config=None):
    rendered = render(StructuredDocument(file_type="PDF", elements=elements, page_count=1))
    chunks = chunk_document(rendered, Words(), title="Đơn hàng", config=config,
                            family=DocFamily.ISO_PROCEDURE)
    for c in chunks:
        assert 0 <= c.char_start < c.char_end <= len(rendered.markdown)
        if c.kind == "TEXT":
            assert rendered.markdown[c.char_start:c.char_end] == c.content
    return chunks


def _content(chunks) -> str:
    return "\n".join(c.content for c in chunks)


def test_step_title_without_body_is_kept_in_a_chunk():
    chunks = _chunks([
        _h("3. Thủ tục", 1),
        _h("3.1 Tiếp nhận đơn", 2),
        _h("3.1.1 Mở hệ thống", 3),
        _h("3.1.2 Kiểm tra thông tin", 3),
        _p(BODY),
        _h("3.2 Giao hàng", 2),
        _h("3.2.1 Bàn giao cho đơn vị vận chuyển", 3),
        _h("3.2.2 Cập nhật mã vận đơn", 3),
    ])
    text = _content(chunks)
    assert "3.1.1 Mở hệ thống" in text
    assert "3.2.1 Bàn giao cho đơn vị vận chuyển" in text
    assert "3.2.2 Cập nhật mã vận đơn" in text


def test_a_parent_heading_is_not_copied_into_content():
    chunks = _chunks([
        _h("3. Thủ tục", 1),
        _h("3.1 Tiếp nhận đơn", 2),
        _h("3.1.1 Mở hệ thống", 3),
        _p(BODY),
    ])
    text = _content(chunks)
    assert "3. Thủ tục" not in text
    assert "3.1 Tiếp nhận đơn" not in text


def test_a_heading_with_a_body_stays_out_of_content():
    chunks = _chunks([_h("1. Mục đích", 1), _p(BODY)])
    assert "1. Mục đích" not in _content(chunks)
    assert chunks[0].section_path == ["1. Mục đích"]


def test_merged_step_titles_appear_once():
    chunks = _chunks([
        _h("3. Thủ tục", 1),
        _h("3.1 Tiếp nhận", 2),
        _p(BODY),
        _h("3.2 Giao hàng", 2),
        _h("3.2.1 Bàn giao", 3),
        _h("3.2.2 Cập nhật mã vận đơn", 3),
    ])
    text = _content(chunks)
    assert text.count("3.2.1 Bàn giao") == 1
    assert text.count("3.2.2 Cập nhật mã vận đơn") == 1


def test_document_made_only_of_headings_still_fails_with_empty_content():
    rendered = render(StructuredDocument(
        file_type="PDF", elements=[_h("1. Mục đích", 1), _h("2. Phạm vi", 1)], page_count=1))
    with pytest.raises(ExtractionError) as error:
        chunk_document(rendered, Words(), config=ChunkConfig())
    assert error.value.code is FailureCode.EMPTY_CONTENT
