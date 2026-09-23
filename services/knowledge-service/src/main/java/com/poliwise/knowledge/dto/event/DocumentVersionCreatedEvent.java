package com.poliwise.knowledge.dto.event;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.time.OffsetDateTime;
import java.util.UUID;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record DocumentVersionCreatedEvent(
        UUID eventId,
        UUID documentId,
        String documentName,
        Integer newVersionNumber,
        String changelog,
        UUID createdBy,
        OffsetDateTime occurredAt
) {

    public static DocumentVersionCreatedEvent create(
            UUID documentId, String documentName,
            Integer newVersionNumber, String changelog, UUID createdBy) {
        return new DocumentVersionCreatedEvent(
                UUID.randomUUID(),
                documentId, documentName, newVersionNumber,
                changelog, createdBy,
                OffsetDateTime.now()
        );
    }
}
