package com.poliwise.feedback.feign.dto;

public record DocumentStatsResponse(
        long totalDocuments,
        long activeDocuments
) {}
