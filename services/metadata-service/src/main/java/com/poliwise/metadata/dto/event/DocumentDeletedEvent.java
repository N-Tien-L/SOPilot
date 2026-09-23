package com.poliwise.metadata.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DocumentDeletedEvent(
        UUID eventId,
        UUID documentId,
        UUID deletedBy,
        OffsetDateTime occurredAt
) {

    public static DocumentDeletedEvent create(UUID documentId, UUID deletedBy) {
        return new DocumentDeletedEvent(
                UUID.randomUUID(),
                documentId,
                deletedBy,
                OffsetDateTime.now()
        );
    }
}