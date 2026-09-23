package com.poliwise.feedback.dto.response;

import java.math.BigDecimal;
import java.util.List;

public record DashboardOverviewResponse(
        long todayQuestions,
        long weekQuestions,
        long monthQuestions,
        long totalFeedbacks,
        BigDecimal satisfactionRate,
        long activeUsersToday,
        long totalUsers,
        long activeUsers,
        long totalDocuments,
        long activeDocuments,
        long unansweredCount,
        List<PopularQuestionResponse> topQuestions,
        List<DocumentPopularityResponse> topDocuments
) {}
