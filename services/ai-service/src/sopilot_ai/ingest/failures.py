"""Failure codes of an ingestion job and their fixed user messages (TECH-V2-ai-service §5.1).

Content codes and their messages come from ``docproc.errors``; this module adds the codes that
only the worker can produce. ``failureMessage`` is never built from an exception.
"""
from __future__ import annotations

from sopilot_ai.docproc.errors import MESSAGES, FailureCode

OBJECT_NOT_FOUND = "OBJECT_NOT_FOUND"
EMBEDDING_ERROR = "EMBEDDING_ERROR"
RETRY_EXHAUSTED = "RETRY_EXHAUSTED"

# Retried automatically with backoff; FAILED only after SOPILOT_INGEST_MAX_ATTEMPTS.
TRANSIENT = frozenset({OBJECT_NOT_FOUND, EMBEDDING_ERROR})

_WORKER_MESSAGES: dict[str, tuple[str, str]] = {
    OBJECT_NOT_FOUND: (
        "Không tìm thấy tệp đã tải lên. Hãy thử lại hoặc tải tệp lên lại.",
        "The uploaded file was not found. Retry or upload the file again.",
    ),
    EMBEDDING_ERROR: (
        "Không tạo được chỉ mục tìm kiếm cho tài liệu. Hãy thử lại sau.",
        "The search index for the document could not be built. Try again later.",
    ),
    RETRY_EXHAUSTED: (
        "Xử lý tài liệu bị gián đoạn nhiều lần. Hãy thử lại sau.",
        "Processing was interrupted repeatedly. Try again later.",
    ),
}


def failure_message(code: str, lang: str = "vi") -> str:
    pair = _WORKER_MESSAGES.get(code)
    if pair is None:
        pair = MESSAGES.get(FailureCode(code)) if code in FailureCode.__members__ else None
    if pair is None:
        pair = MESSAGES[FailureCode.EXTRACTION_ERROR]
    return pair[0] if lang == "vi" else pair[1]
