package com.poliwise.auth.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserRevokedEvent(
        UUID eventId,
        UUID userId,
        String username,
        UUID revokedBy,
        String reason,
        OffsetDateTime occurredAt
) {
    public static UserRevokedEvent create(
            UUID userId, String username, UUID revokedBy, String reason) {
        return new UserRevokedEvent(
                UUID.randomUUID(),
                userId,
                username,
                revokedBy,
                reason,
                OffsetDateTime.now()
        );
    }
}
