package com.poliwise.auth.dto.event;

import com.poliwise.auth.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserRegisteredEvent(
        UUID eventId,
        UUID userId,
        String username,
        String email,
        UserRole role,
        UUID registeredBy,
        OffsetDateTime occurredAt
) {

    public static UserRegisteredEvent create(
            UUID userId, String username, String email,
            UserRole role, UUID registeredBy) {
        return new UserRegisteredEvent(
                UUID.randomUUID(),
                userId, username, email,
                role,
                registeredBy,
                OffsetDateTime.now()
        );
    }

    public static UserRegisteredEvent createSelfRegistered(
            UUID userId, String username, String email, UserRole role) {
        return new UserRegisteredEvent(
                UUID.randomUUID(),
                userId, username, email,
                role,
                null,
                OffsetDateTime.now()
        );
    }
}