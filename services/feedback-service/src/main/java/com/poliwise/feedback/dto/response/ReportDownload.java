package com.poliwise.feedback.dto.response;

import com.poliwise.feedback.enums.ExportFormat;

import java.io.InputStream;

public record ReportDownload(
        InputStream inputStream,
        ExportFormat format,
        long contentLength
) {
}
