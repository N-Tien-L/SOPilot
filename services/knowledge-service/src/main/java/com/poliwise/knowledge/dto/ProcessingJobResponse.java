package com.poliwise.knowledge.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ProcessingJobResponse(
        UUID id,
        UUID documentId,
        String jobType,
        String status,
        Integer progressPercent,
        OffsetDateTime startedAt,
        OffsetDateTime completedAt,
        Boolean success,
        String errorMessage,
        Integer retryCount
) {}