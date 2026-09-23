package com.poliwise.feedback.feign.dto;

public record UserStatsResponse(
        long totalUsers,
        long activeUsers
) {}
