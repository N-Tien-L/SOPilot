package com.poliwise.knowledge.dto;

public record DocumentStatsResponse(
        long totalDocuments,
        long activeDocuments
) {}
