package com.poliwise.feedback.dto.request;

import com.poliwise.feedback.enums.FeedbackType;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.UUID;

public record FeedbackRequest(
        @NotNull(message = "Message ID is required")
        UUID messageId,

        @NotNull(message = "Conversation ID is required")
        UUID conversationId,

        @NotNull(message = "Feedback type is required")
        FeedbackType type,

        @Size(max = 1000, message = "Comment must not exceed 1000 characters")
        String comment
) {}
