package com.poliwise.user.dto.event;

import com.poliwise.user.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserRevokedEvent(
        UUID eventId,
        UUID userId,
        String username,
        UserRole role,
        UUID revokedBy,
        String reason,
        OffsetDateTime occurredAt
) {

    public static UserRevokedEvent create(
            UUID userId, String username,
            UserRole role, UUID revokedBy, String reason) {
        return new UserRevokedEvent(
                UUID.randomUUID(),
                userId, username,
                role, revokedBy,
                reason != null ? reason : "Account revoked by administrator",
                OffsetDateTime.now()
        );
    }
}

