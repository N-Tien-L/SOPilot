package com.poliwise.feedback.dto.response;

import com.poliwise.feedback.entity.Feedback;
import com.poliwise.feedback.enums.FeedbackType;

import java.time.Instant;
import java.util.UUID;

public record FeedbackResponse(
        UUID id,
        UUID userId,
        UUID messageId,
        UUID conversationId,
        FeedbackType type,
        String comment,
        String questionText,
        String answerText,
        Instant createdAt
) {
    public static FeedbackResponse fromEntity(Feedback f) {
        return new FeedbackResponse(
                f.getId(), f.getUserId(), f.getMessageId(), f.getConversationId(),
                f.getType(), f.getComment(), f.getQuestionText(), f.getAnswerText(), f.getCreatedAt()
        );
    }
}
