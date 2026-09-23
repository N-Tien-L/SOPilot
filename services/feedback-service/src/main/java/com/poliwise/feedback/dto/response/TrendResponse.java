package com.poliwise.feedback.dto.response;

import java.time.LocalDate;
import java.util.List;

public record TrendResponse(
        LocalDate date,
        long totalQuestions,
        long totalFeedbacks,
        Integer avgResponseTimeMs,
        long uniqueUsers,
        long likes,
        long dislikes,
        List<DepartmentStatsResponse> departmentBreakdown
) {}
