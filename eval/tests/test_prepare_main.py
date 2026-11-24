import pytest

from sopilot_eval.prepare_main import _loose, _strip_markdown, locate, pages_for

TEXT = (
    "# 4.3 Phiên bản\n\n- 01/01: lần ban hành 01, lần sửa đổi 01.\n\n"
    "| 2 | Sổ phân phối | Thư ký | 3 năm, sau đó lập sổ mới |\n\n"
    "4. Send the meeting invite with proper advance notice. We recommend 72 hours.\n\n"
    "Nhắc lại: 3 năm."
)


def test_locate_exact_and_whitespace_flexible():
    start, end = locate(TEXT, "01/01: lần ban hành 01, lần sửa đổi 01.")
    assert TEXT[start:end] == "01/01: lần ban hành 01, lần sửa đổi 01."
    start, end = locate(TEXT, "Thư ký |  3 năm,\nsau đó lập sổ mới")
    assert TEXT[start:end] == "Thư ký | 3 năm, sau đó lập sổ mới"


def test_locate_rejects_ambiguous_quote_without_anchor():
    with pytest.raises(ValueError, match="ambiguous"):
        locate(TEXT, "3 năm")
    start, _ = locate(TEXT, "3 năm", after="Nhắc lại")
    assert TEXT[start - 10:start] == "Nhắc lại: "


def test_locate_reports_missing_quote():
    with pytest.raises(ValueError, match="not found"):
        locate(TEXT, "không có trong văn bản")


def test_markdown_quotes_rebase_onto_rendered_text():
    old = "1. **Send the meeting invite with proper advance notice.** We recommend 72 hours."
    assert _strip_markdown(old) == "Send the meeting invite with proper advance notice. We recommend 72 hours."
    start, end = _loose(TEXT, old)
    assert TEXT[start:end] == "Send the meeting invite with proper advance notice. We recommend 72 hours."
    assert _strip_markdown("see [Meeting agendas](meetings/#4) now") == "see Meeting agendas now"


def test_pages_for_uses_exclusive_end():
    pmap = [{"page": 1, "start_char": 0, "end_char": 10}, {"page": 2, "start_char": 10, "end_char": 20}]
    assert pages_for(pmap, 2, 10) == [1]
    assert pages_for(pmap, 9, 12) == [1, 2]
    assert pages_for(None, 0, 5) is None
