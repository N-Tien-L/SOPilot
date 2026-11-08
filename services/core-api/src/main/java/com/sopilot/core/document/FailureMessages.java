package com.sopilot.core.document;

import java.util.Map;

/**
 * Fixed user-facing sentence per failure code (TECH §5.5, §6). The text ai-service sends is never
 * stored or returned, so internal errors cannot leak through {@code failureMessage}.
 */
final class FailureMessages {

    private static final String GENERIC = "Xử lý tài liệu thất bại. Hãy thử lại hoặc thay bằng một tệp khác.";

    private static final Map<String, String> BY_CODE = Map.ofEntries(
            Map.entry("NO_TEXT_LAYER", "PDF không có lớp chữ (bản scan). Hãy tải bản PDF có thể chọn chữ."),
            Map.entry("ENCRYPTED_PDF", "PDF được mã hóa hoặc đặt mật khẩu. Hãy tải bản không khóa."),
            Map.entry("CORRUPT_FILE", "Tệp bị hỏng hoặc không đọc được. Hãy xuất lại tệp rồi tải lên."),
            Map.entry("UNSUPPORTED_TYPE", "Loại tệp này không được hỗ trợ. Hãy dùng PDF có lớp chữ hoặc Markdown (.md)."),
            Map.entry("INVALID_ENCODING", "Tệp Markdown không phải UTF-8. Hãy lưu lại bằng UTF-8."),
            Map.entry("EMPTY_CONTENT", "Không trích xuất được nội dung từ tệp."),
            Map.entry("EXTRACTION_ERROR", "Trích xuất nội dung thất bại. Hãy thử lại."),
            Map.entry("EMBEDDING_ERROR", "Dịch vụ tạo vector đang lỗi. Hãy thử lại sau."),
            Map.entry("OBJECT_NOT_FOUND", "Không tìm thấy tệp trong kho lưu trữ. Hãy thử lại."),
            Map.entry("RETRY_EXHAUSTED", "Đã thử lại nhiều lần nhưng không thành công. Hãy thử lại sau."),
            Map.entry("DISPATCH_FAILED", "Không gửi được tài liệu sang dịch vụ xử lý. Hãy thử lại."));

    private FailureMessages() {
    }

    static String forCode(String code) {
        return BY_CODE.getOrDefault(code, GENERIC);
    }

    /** Codes outside the known set are stored as a generic code, so clients see a bounded vocabulary. */
    static String normalize(String code) {
        return code != null && BY_CODE.containsKey(code) ? code : "EXTRACTION_ERROR";
    }
}
