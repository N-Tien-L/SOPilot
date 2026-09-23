package com.poliwise.feedback.controller;

import com.poliwise.feedback.dto.request.ReportExportRequest;
import com.poliwise.feedback.dto.response.ApiResponse;
import com.poliwise.feedback.dto.response.ReportDownload;
import com.poliwise.feedback.dto.response.ReportExportResponse;
import com.poliwise.feedback.enums.ExportFormat;
import com.poliwise.feedback.security.JwtAuthenticationToken;
import com.poliwise.feedback.security.UserPrincipal;
import com.poliwise.feedback.service.ReportExportService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/reports")
public class ReportController {

    private final ReportExportService reportExportService;

    public ReportController(ReportExportService reportExportService) {
        this.reportExportService = reportExportService;
    }

    @PostMapping("/export")
    public ResponseEntity<ApiResponse<ReportExportResponse>> createReport(
            @Valid @RequestBody ReportExportRequest request, Authentication authentication) {
        UUID userId = getUserId(authentication);
        return ResponseEntity.accepted().body(ApiResponse.success(reportExportService.createReport(userId, request), "Report generation started"));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<ReportExportResponse>> getStatus(@PathVariable UUID id) {
        return ResponseEntity.ok(ApiResponse.success(reportExportService.getReportStatus(id)));
    }

    @GetMapping("/{id}/download")
    public ResponseEntity<StreamingResponseBody> download(@PathVariable UUID id, Authentication authentication) {
        UUID userId = getUserId(authentication);
        boolean isAdmin = "ADMIN".equals(getRole(authentication));
        ReportDownload download = reportExportService.openReport(id, userId, isAdmin);
        String extension = extensionFor(download.format());
        String filename = "report-" + id + "." + extension;
        StreamingResponseBody body = outputStream -> {
            try (var inputStream = download.inputStream()) {
                inputStream.transferTo(outputStream);
            }
        };
        ResponseEntity.BodyBuilder response = ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .contentType(mediaTypeFor(download.format()));
        if (download.contentLength() >= 0) response.contentLength(download.contentLength());
        return response.body(body);
    }

    @GetMapping
    public ResponseEntity<ApiResponse<Page<ReportExportResponse>>> getMyReports(
            Authentication authentication, @PageableDefault(size = 20) Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.success(reportExportService.getReportsByUser(getUserId(authentication), pageable)));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteReport(@PathVariable UUID id, Authentication authentication) {
        UUID userId = getUserId(authentication);
        boolean isAdmin = "ADMIN".equals(getRole(authentication));
        reportExportService.deleteReport(id, userId, isAdmin);
        return ResponseEntity.noContent().build();
    }

    private UUID getUserId(Authentication authentication) {
        if (authentication instanceof JwtAuthenticationToken jwtAuth) return ((UserPrincipal) jwtAuth.getPrincipal()).getUserId();
        throw new IllegalStateException("Invalid authentication type");
    }

    private String getRole(Authentication authentication) {
        if (authentication instanceof JwtAuthenticationToken jwtAuth) return ((UserPrincipal) jwtAuth.getPrincipal()).getRole();
        return null;
    }

    private String extensionFor(ExportFormat format) {
        return switch (format) {
            case CSV -> "csv";
            case JSON -> "json";
            case PDF -> "pdf";
            case XLSX -> "xlsx";
        };
    }

    private MediaType mediaTypeFor(ExportFormat format) {
        return switch (format) {
            case CSV -> MediaType.parseMediaType("text/csv; charset=UTF-8");
            case JSON -> MediaType.APPLICATION_JSON;
            case PDF -> MediaType.APPLICATION_PDF;
            case XLSX -> MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        };
    }
}
