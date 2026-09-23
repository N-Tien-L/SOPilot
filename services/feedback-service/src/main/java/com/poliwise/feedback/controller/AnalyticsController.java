package com.poliwise.feedback.controller;

import com.poliwise.feedback.dto.request.AnalyticsRequest;
import com.poliwise.feedback.dto.response.*;
import com.poliwise.feedback.service.AnalyticsService;
import com.poliwise.feedback.service.DashboardService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/analytics")
public class AnalyticsController {

    private final AnalyticsService analyticsService;
    private final DashboardService dashboardService;

    public AnalyticsController(AnalyticsService analyticsService, DashboardService dashboardService) {
        this.analyticsService = analyticsService;
        this.dashboardService = dashboardService;
    }

    @GetMapping("/dashboard")
    public ResponseEntity<ApiResponse<DashboardOverviewResponse>> getDashboard() {
        return ResponseEntity.ok(ApiResponse.success(dashboardService.getOverview()));
    }

    @GetMapping("/overview")
    public ResponseEntity<ApiResponse<DashboardOverviewResponse>> getOverview() {
        return ResponseEntity.ok(ApiResponse.success(dashboardService.getOverview()));
    }

    @GetMapping("/top-questions")
    public ResponseEntity<ApiResponse<List<PopularQuestionResponse>>> getTopQuestions(
            @RequestParam(defaultValue = "10") int limit) {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getTopQuestions(limit, null, null)));
    }

    @GetMapping("/top-documents")
    public ResponseEntity<ApiResponse<List<DocumentPopularityResponse>>> getTopDocuments(
            @RequestParam(defaultValue = "10") int limit) {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getTopDocuments(limit)));
    }

    @GetMapping("/summary")
    public ResponseEntity<ApiResponse<AnalyticsSummaryResponse>> getSummary(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fromDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate toDate,
            @RequestParam(required = false) UUID departmentId) {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getSummary(new AnalyticsRequest(fromDate, toDate, departmentId))));
    }

    @GetMapping("/questions")
    public ResponseEntity<ApiResponse<List<PopularQuestionResponse>>> getTopQuestionsFull(
            @RequestParam(defaultValue = "10") int limit,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getTopQuestions(limit, from, to)));
    }

    @GetMapping("/documents")
    public ResponseEntity<ApiResponse<List<DocumentPopularityResponse>>> getTopDocumentsFull(
            @RequestParam(defaultValue = "10") int limit) {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getTopDocuments(limit)));
    }

    @GetMapping("/feedback")
    public ResponseEntity<ApiResponse<AnalyticsSummaryResponse>> getFeedbackAnalysis(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fromDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate toDate) {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getSummary(new AnalyticsRequest(fromDate, toDate, null))));
    }

    @GetMapping("/departments/{deptId}")
    public ResponseEntity<ApiResponse<DepartmentStatsResponse>> getDepartmentStats(
            @PathVariable UUID deptId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        LocalDate targetDate = date != null ? date : LocalDate.now();
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getDepartmentStats(deptId, targetDate)));
    }

    @GetMapping("/document-views")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getDocumentViewStats(
            @RequestParam(defaultValue = "30") int days) {
        Map<String, Object> stats = analyticsService.getDocumentViewStats(days);
        return ResponseEntity.ok(ApiResponse.success(stats));
    }

    @GetMapping("/trends")
    public ResponseEntity<ApiResponse<List<TrendResponse>>> getTrends(
            @RequestParam(defaultValue = "30") int days) {
        return ResponseEntity.ok(ApiResponse.success(analyticsService.getTrends(days)));
    }

    @GetMapping("/unanswered")
    public ResponseEntity<ApiResponse<org.springframework.data.domain.Page<UnansweredQuestionResponse>>> getUnanswered(
            @RequestParam(required = false) String status,
            @org.springframework.data.web.PageableDefault(size = 20) org.springframework.data.domain.Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.success(dashboardService.getUnansweredQuestions(pageable, status)));
    }

    @PutMapping("/unanswered/{id}/resolve")
    public ResponseEntity<ApiResponse<Void>> resolveUnanswered(
            @PathVariable UUID id,
            @RequestBody Map<String, String> request) {
        UUID resolvedBy = request.get("resolvedBy") != null ? UUID.fromString(request.get("resolvedBy")) : null;
        dashboardService.resolveUnanswered(id, resolvedBy, request.get("answer"));
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @PutMapping("/unanswered/{id}/reject")
    public ResponseEntity<ApiResponse<Void>> rejectUnanswered(
            @PathVariable UUID id,
            @RequestBody Map<String, String> request) {
        UUID resolvedBy = request.get("resolvedBy") != null ? UUID.fromString(request.get("resolvedBy")) : null;
        dashboardService.rejectUnanswered(id, resolvedBy);
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
