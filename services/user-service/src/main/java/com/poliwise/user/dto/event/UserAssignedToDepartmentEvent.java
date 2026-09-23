package com.poliwise.user.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserAssignedToDepartmentEvent(
        UUID eventId,
        UUID userId,
        String username,
        UUID departmentId,
        String departmentName,
        UUID assignedBy,
        OffsetDateTime occurredAt
) {
    public static UserAssignedToDepartmentEvent create(
            UUID userId, String username, UUID departmentId, String departmentName, UUID assignedBy) {
        return new UserAssignedToDepartmentEvent(
                UUID.randomUUID(),
                userId,
                username,
                departmentId,
                departmentName,
                assignedBy,
                OffsetDateTime.now()
        );
    }
}
