from __future__ import annotations

import sys

import pytest

from sopilot_ai.docproc import ExtractionError, FailureCode, extract
from sopilot_ai.docproc.errors import MESSAGES


@pytest.mark.parametrize("name", ["a.docx", "a.txt", "a.doc", "a", "a.pdf.exe", "a.rtf"])
def test_unsupported_types_fail_before_any_parser(name, monkeypatch):
    sys.modules.pop("sopilot_ai.docproc.extract.pdf", None)
    with pytest.raises(ExtractionError) as exc:
        extract(b"anything", name)
    assert exc.value.code is FailureCode.UNSUPPORTED_TYPE
    assert "sopilot_ai.docproc.extract.pdf" not in sys.modules  # PDF library never imported


def test_type_is_decided_by_extension_case_insensitively():
    assert extract(b"# T\n", "NOTES.MD").file_type == "MD"
    assert extract(b"# T\n", "notes.markdown").file_type == "MD"


def test_every_failure_code_has_fixed_vi_and_en_messages():
    for code in FailureCode:
        vi, en = MESSAGES[code]
        assert vi and en and vi != en
    err = ExtractionError(FailureCode.NO_TEXT_LAYER)
    assert "lớp chữ" in err.message_vi and "text layer" in err.message_en
