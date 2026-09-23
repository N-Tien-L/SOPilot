package com.poliwise.auth.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserDeactivatedEvent(
        UUID eventId,
        UUID userId,
        String username,
        UUID deactivatedBy,
        OffsetDateTime occurredAt
) {
    public static UserDeactivatedEvent create(
            UUID userId, String username, UUID deactivatedBy) {
        return new UserDeactivatedEvent(
                UUID.randomUUID(),
                userId,
                username,
                deactivatedBy,
                OffsetDateTime.now()
        );
    }
}
