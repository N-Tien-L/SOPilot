package com.poliwise.knowledge.dto.event;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.time.OffsetDateTime;
import java.util.UUID;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record DocumentDeletedEvent(
        UUID eventId,
        UUID documentId,
        String documentName,
        UUID deletedBy,
        OffsetDateTime occurredAt
) {
    public static DocumentDeletedEvent create(UUID documentId, String documentName, UUID deletedBy) {
        return new DocumentDeletedEvent(
                UUID.randomUUID(),
                documentId,
                documentName,
                deletedBy,
                OffsetDateTime.now()
        );
    }
}