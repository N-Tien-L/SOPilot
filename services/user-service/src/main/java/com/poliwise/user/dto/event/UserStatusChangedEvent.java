package com.poliwise.user.dto.event;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserStatusChangedEvent(
        UUID eventId,
        UUID userId,
        String username,
        AccountStatus previousStatus,
        AccountStatus newStatus,
        UserRole role,
        UUID changedBy,
        OffsetDateTime occurredAt
) {

    public static UserStatusChangedEvent create(
            UUID userId, String username,
            AccountStatus previousStatus, AccountStatus newStatus,
            UserRole role, UUID changedBy) {
        return new UserStatusChangedEvent(
                UUID.randomUUID(),
                userId, username,
                previousStatus, newStatus,
                role, changedBy,
                OffsetDateTime.now()
        );
    }
}
