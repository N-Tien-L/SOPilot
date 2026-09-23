package com.poliwise.feedback.dto.response;

import com.poliwise.feedback.entity.PopularQuestion;

import java.time.Instant;
import java.util.UUID;

public record PopularQuestionResponse(
        UUID id,
        String questionSample,
        int askCount,
        int totalLikes,
        int totalDislikes,
        String commonSourceDocuments,
        String detectedCategory,
        Instant lastAskedAt
) {
    public static PopularQuestionResponse fromEntity(PopularQuestion pq) {
        return new PopularQuestionResponse(
                pq.getId(), pq.getQuestionSample(), pq.getAskCount() != null ? pq.getAskCount() : 0,
                pq.getTotalLikes() != null ? pq.getTotalLikes() : 0, pq.getTotalDislikes() != null ? pq.getTotalDislikes() : 0,
                pq.getCommonSourceDocuments(), pq.getDetectedCategory(), pq.getLastAskedAt()
        );
    }
}
