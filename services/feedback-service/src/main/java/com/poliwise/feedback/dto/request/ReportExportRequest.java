package com.poliwise.feedback.dto.request;

import com.poliwise.feedback.enums.ExportFormat;
import com.poliwise.feedback.enums.ReportType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;
import java.util.UUID;

public record ReportExportRequest(
        @NotNull(message = "Report type is required")
        ReportType reportType,

        @NotBlank(message = "Title is required")
        @Size(max = 255, message = "Title must not exceed 255 characters")
        String title,

        LocalDate dateFrom,
        LocalDate dateTo,
        UUID departmentId,

        @NotNull(message = "Export format is required")
        ExportFormat format
) {}
