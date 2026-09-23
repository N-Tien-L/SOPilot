package com.poliwise.feedback.controller;

import com.poliwise.feedback.dto.request.AuditLogSearchRequest;
import com.poliwise.feedback.dto.response.ApiResponse;
import com.poliwise.feedback.dto.response.AuditLogResponse;
import com.poliwise.feedback.service.AuditLogService;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/analytics/audit-logs")
public class AuditController {

    private final AuditLogService auditLogService;

    public AuditController(AuditLogService auditLogService) {
        this.auditLogService = auditLogService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<Page<AuditLogResponse>>> search(
            AuditLogSearchRequest request,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(required = false) Integer limit) {
        int size = (limit != null && limit > 0) ? limit : 50;
        int pageNum = page < 0 ? 0 : page;
        Pageable pageable = PageRequest.of(pageNum, size);
        return ResponseEntity.ok(ApiResponse.success(auditLogService.searchLogs(request, pageable)));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<AuditLogResponse>> getById(@PathVariable UUID id) {
        AuditLogResponse log = auditLogService.getAuditLogById(id);
        if (log == null) return ResponseEntity.notFound().build();
        return ResponseEntity.ok(ApiResponse.success(log));
    }
}
