package com.poliwise.feedback.controller;

import com.poliwise.feedback.dto.response.*;
import com.poliwise.feedback.enums.UnansweredStatus;
import com.poliwise.feedback.security.JwtAuthenticationToken;
import com.poliwise.feedback.service.DashboardService;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.core.context.SecurityContextHolder;

@RestController
@RequestMapping("/api/v1/dashboard")
public class DashboardController {

    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
    }

    @GetMapping("/overview")
    public ResponseEntity<ApiResponse<DashboardOverviewResponse>> getOverview() {
        return ResponseEntity.ok(ApiResponse.success(dashboardService.getOverview()));
    }

    @GetMapping("/trends")
    public ResponseEntity<ApiResponse<List<TrendResponse>>> getTrends(@RequestParam(defaultValue = "30") int days) {
        return ResponseEntity.ok(ApiResponse.success(dashboardService.getTrends(days)));
    }

    @GetMapping("/unanswered")
    public ResponseEntity<ApiResponse<Page<UnansweredQuestionResponse>>> getUnanswered(
            @RequestParam(required = false) String status,
            @PageableDefault(size = 20) Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.success(dashboardService.getUnansweredQuestions(pageable, status)));
    }

    @PutMapping("/unanswered/{id}/resolve")
    public ResponseEntity<ApiResponse<UnansweredQuestionResponse>> resolveUnanswered(
            @PathVariable UUID id,
            @RequestBody(required = false) Map<String, String> body) {
        UUID userId = currentUserId();
        String answer = body != null ? body.get("answer") : null;
        return ResponseEntity.ok(ApiResponse.success(dashboardService.resolveUnanswered(id, userId, answer)));
    }

    @PutMapping("/unanswered/{id}/reject")
    public ResponseEntity<ApiResponse<UnansweredQuestionResponse>> rejectUnanswered(@PathVariable UUID id) {
        UUID userId = currentUserId();
        return ResponseEntity.ok(ApiResponse.success(dashboardService.rejectUnanswered(id, userId)));
    }

    private UUID currentUserId() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            Object principal = jwt.getPrincipal();
            if (principal instanceof com.poliwise.feedback.security.UserPrincipal userPrincipal) {
                return userPrincipal.getUserId();
            }
        }
        return null;
    }
}
