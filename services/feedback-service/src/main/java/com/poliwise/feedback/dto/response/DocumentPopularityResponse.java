package com.poliwise.feedback.dto.response;

import com.poliwise.feedback.entity.DocumentPopularity;

import java.time.Instant;
import java.util.UUID;

public record DocumentPopularityResponse(
        UUID id,
        UUID documentId,
        int totalCitations,
        int uniqueQuestionsCited,
        int citationsWithLikes,
        int citationsWithDislikes,
        Instant firstCitedAt,
        Instant lastCitedAt,
        int citationsLast7Days,
        int citationsLast30Days
) {
    public static DocumentPopularityResponse fromEntity(DocumentPopularity dp) {
        return new DocumentPopularityResponse(
                dp.getId(), dp.getDocumentId(),
                dp.getTotalCitations() != null ? dp.getTotalCitations() : 0,
                dp.getUniqueQuestionsCited() != null ? dp.getUniqueQuestionsCited() : 0,
                dp.getCitationsWithLikes() != null ? dp.getCitationsWithLikes() : 0,
                dp.getCitationsWithDislikes() != null ? dp.getCitationsWithDislikes() : 0,
                dp.getFirstCitedAt(), dp.getLastCitedAt(),
                dp.getCitationsLast7Days() != null ? dp.getCitationsLast7Days() : 0,
                dp.getCitationsLast30Days() != null ? dp.getCitationsLast30Days() : 0
        );
    }
}
