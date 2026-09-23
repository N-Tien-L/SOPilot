package com.poliwise.user.dto;

public record UserStatsResponse(
        long totalUsers,
        long activeUsers
) {}
