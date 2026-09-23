package com.poliwise.feedback.dto.response;

import com.poliwise.feedback.entity.ReportExport;
import com.poliwise.feedback.enums.ExportFormat;
import com.poliwise.feedback.enums.ExportStatus;
import com.poliwise.feedback.enums.ReportType;

import java.time.Instant;
import java.util.UUID;

public record ReportExportResponse(
        UUID id,
        ReportType reportType,
        String title,
        ExportFormat format,
        ExportStatus status,
        String fileKey,
        Integer fileSizeBytes,
        UUID requestedBy,
        Instant createdAt,
        Instant completedAt,
        Instant expiresAt,
        String errorMessage
) {
    public static ReportExportResponse fromEntity(ReportExport r) {
        return new ReportExportResponse(
                r.getId(), r.getReportType(), r.getTitle(), r.getFormat(),
                r.getStatus(), r.getFileKey(), r.getFileSizeBytes(),
                r.getRequestedBy(), r.getCreatedAt(), r.getCompletedAt(),
                r.getExpiresAt(), r.getErrorMessage()
        );
    }
}
