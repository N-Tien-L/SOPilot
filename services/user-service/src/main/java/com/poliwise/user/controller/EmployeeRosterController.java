package com.poliwise.user.controller;

import com.poliwise.user.dto.roster.RosterImportResponse;
import com.poliwise.user.dto.roster.RosterResponse;
import com.poliwise.user.enums.RosterStatus;
import com.poliwise.user.security.JwtAuthenticationToken;
import com.poliwise.user.service.EmployeeRosterService;
import com.poliwise.user.service.RosterExcelService;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.UUID;

/**
 * REST Controller cho Quản lý Danh bạ Nhân sự (Employee Roster).
 * Chỉ dành cho ADMIN hoặc HR.
 */
@RestController
@RequestMapping("/api/v1/users/roster")
@PreAuthorize("hasAnyRole('ADMIN', 'HR')")
public class EmployeeRosterController {

    private final EmployeeRosterService employeeRosterService;
    private final RosterExcelService rosterExcelService;

    public EmployeeRosterController(
            EmployeeRosterService employeeRosterService,
            RosterExcelService rosterExcelService) {
        this.employeeRosterService = employeeRosterService;
        this.rosterExcelService = rosterExcelService;
    }

    private UUID getCurrentUserId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            return jwt.getUserId();
        }
        return null;
    }

    /**
     * Tải file Excel mẫu gồm 2 sheet: Template nhập liệu & Danh mục phòng ban.
     * GET /api/v1/users/roster/template
     */
    @GetMapping("/template")
    public ResponseEntity<byte[]> downloadTemplate() {
        byte[] excelBytes = rosterExcelService.generateTemplate();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"employee_roster_template.xlsx\"")
                .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                .body(excelBytes);
    }

    /**
     * Import danh bạ nhân sự từ file Excel (.xlsx).
     * POST /api/v1/users/roster/import
     */
    @PostMapping(value = "/import", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<RosterImportResponse> importRoster(@RequestParam("file") MultipartFile file) throws IOException {
        UUID currentUserId = getCurrentUserId();
        RosterImportResponse response = rosterExcelService.importRoster(file.getInputStream(), currentUserId);
        return ResponseEntity.ok(response);
    }

    /**
     * Tìm kiếm và phân trang danh bạ nhân sự.
     * GET /api/v1/users/roster
     */
    @GetMapping
    public ResponseEntity<Page<RosterResponse>> searchRoster(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) UUID departmentId,
            @RequestParam(required = false) RosterStatus status,
            @RequestParam(required = false) Boolean isClaimed,
            @PageableDefault(size = 20, sort = "createdAt", direction = Sort.Direction.DESC) Pageable pageable) {
        Page<RosterResponse> result = employeeRosterService.searchRoster(keyword, departmentId, status, isClaimed, pageable);
        return ResponseEntity.ok(result);
    }

    /**
     * Lấy chi tiết bản ghi danh bạ nhân sự theo ID.
     * GET /api/v1/users/roster/{id}
     */
    @GetMapping("/{id}")
    public ResponseEntity<RosterResponse> getById(@PathVariable UUID id) {
        return ResponseEntity.ok(employeeRosterService.getById(id));
    }

    /**
     * Vô hiệu hóa bản ghi danh bạ nhân sự.
     * DELETE /api/v1/users/roster/{id}
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deactivate(@PathVariable UUID id) {
        UUID currentUserId = getCurrentUserId();
        employeeRosterService.deactivateRoster(id, currentUserId);
        return ResponseEntity.noContent().build();
    }
}
