package com.poliwise.user.dto.event;

import com.poliwise.user.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserRegisteredEvent(
        UUID eventId,
        UUID userId,
        String username,
        String email,
        UserRole role,
        OffsetDateTime occurredAt
) {
    public static UserRegisteredEvent create(UUID userId, String username, String email, UserRole role) {
        return new UserRegisteredEvent(
                UUID.randomUUID(),
                userId,
                username,
                email,
                role,
                OffsetDateTime.now()
        );
    }
}
