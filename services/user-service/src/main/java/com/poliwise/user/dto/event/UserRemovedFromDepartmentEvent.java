package com.poliwise.user.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserRemovedFromDepartmentEvent(
        UUID eventId,
        UUID userId,
        String username,
        UUID departmentId,
        String departmentName,
        UUID removedBy,
        OffsetDateTime occurredAt
) {
    public static UserRemovedFromDepartmentEvent create(
            UUID userId, String username, UUID departmentId, String departmentName, UUID removedBy) {
        return new UserRemovedFromDepartmentEvent(
                UUID.randomUUID(),
                userId,
                username,
                departmentId,
                departmentName,
                removedBy,
                OffsetDateTime.now()
        );
    }
}
