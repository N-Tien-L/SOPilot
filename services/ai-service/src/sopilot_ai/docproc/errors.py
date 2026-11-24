"""Deterministic extraction failures with fixed user-facing messages (TECH-V2-ai-service §5.1)."""
from __future__ import annotations

from enum import StrEnum


class FailureCode(StrEnum):
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
    NO_TEXT_LAYER = "NO_TEXT_LAYER"
    ENCRYPTED_PDF = "ENCRYPTED_PDF"
    CORRUPT_FILE = "CORRUPT_FILE"
    INVALID_ENCODING = "INVALID_ENCODING"
    EMPTY_CONTENT = "EMPTY_CONTENT"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"


# (Vietnamese, English). Never built from an exception message.
MESSAGES: dict[FailureCode, tuple[str, str]] = {
    FailureCode.UNSUPPORTED_TYPE: (
        "Định dạng tệp chưa được hỗ trợ. Hãy dùng PDF có lớp chữ hoặc Markdown.",
        "This file type is not supported. Use a text-based PDF or Markdown.",
    ),
    FailureCode.NO_TEXT_LAYER: (
        "PDF không có lớp chữ (có thể là bản quét). Hãy xuất lại PDF có lớp chữ.",
        "The PDF has no text layer (it may be a scan). Export a text-based PDF.",
    ),
    FailureCode.ENCRYPTED_PDF: (
        "PDF được bảo vệ bằng mật khẩu. Hãy gỡ mật khẩu rồi tải lên lại.",
        "The PDF is password-protected. Remove the password and upload again.",
    ),
    FailureCode.CORRUPT_FILE: (
        "Tệp bị hỏng hoặc không đọc được.",
        "The file is corrupt or unreadable.",
    ),
    FailureCode.INVALID_ENCODING: (
        "Tệp Markdown phải được lưu bằng UTF-8.",
        "The Markdown file must be saved as UTF-8.",
    ),
    FailureCode.EMPTY_CONTENT: (
        "Không tìm thấy nội dung để lập chỉ mục.",
        "No indexable content was found.",
    ),
    FailureCode.EXTRACTION_ERROR: (
        "Không trích xuất được nội dung tài liệu.",
        "The document content could not be extracted.",
    ),
}


class ExtractionError(Exception):
    """Raised for content-dependent, retry-safe-to-skip failures."""

    def __init__(self, code: FailureCode) -> None:
        super().__init__(code.value)
        self.code = code

    @property
    def message_vi(self) -> str:
        return MESSAGES[self.code][0]

    @property
    def message_en(self) -> str:
        return MESSAGES[self.code][1]
