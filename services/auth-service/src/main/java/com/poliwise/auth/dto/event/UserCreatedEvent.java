package com.poliwise.auth.dto.event;

import com.poliwise.auth.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserCreatedEvent(
        UUID eventId,
        UUID userId,
        String username,
        String email,
        UserRole role,
        UUID createdBy,
        OffsetDateTime occurredAt
) {
    public static UserCreatedEvent create(
            UUID userId, String username, String email,
            UserRole role, UUID createdBy) {
        return new UserCreatedEvent(
                UUID.randomUUID(),
                userId, username, email,
                role,
                createdBy,
                OffsetDateTime.now()
        );
    }
}
