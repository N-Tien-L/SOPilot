package com.poliwise.feedback.dto.response;

import java.math.BigDecimal;
import java.util.UUID;

public record DepartmentStatsResponse(
        UUID departmentId,
        String departmentName,
        long totalQuestions,
        long uniqueUsers,
        long likes,
        long dislikes,
        BigDecimal satisfactionRate
) {}
