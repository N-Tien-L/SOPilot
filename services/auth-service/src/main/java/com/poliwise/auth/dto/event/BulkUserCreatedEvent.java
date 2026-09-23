package com.poliwise.auth.dto.event;

import com.poliwise.auth.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record BulkUserCreatedEvent(
        UUID eventId,
        List<UserItem> users,
        UUID createdBy,
        int successCount,
        int failCount,
        OffsetDateTime occurredAt
) {
    public record UserItem(
            UUID userId,
            String username,
            String email,
            UserRole role
    ) {}

    public static BulkUserCreatedEvent create(
            List<UserItem> users, UUID createdBy, int successCount, int failCount) {
        return new BulkUserCreatedEvent(
                UUID.randomUUID(),
                users,
                createdBy,
                successCount,
                failCount,
                OffsetDateTime.now()
        );
    }
}
