package com.poliwise.feedback.dto.response;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

public record AnalyticsSummaryResponse(
        long totalQuestions,
        long totalFeedbacks,
        long totalLikes,
        long totalDislikes,
        BigDecimal satisfactionRate,
        Integer avgResponseTimeMs,
        List<TopCategory> topCategories,
        LocalDate dateFrom,
        LocalDate dateTo
) {
    public record TopCategory(String category, Long count) {}
}
