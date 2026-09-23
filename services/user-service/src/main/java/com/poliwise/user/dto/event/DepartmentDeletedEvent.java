package com.poliwise.user.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DepartmentDeletedEvent(
        UUID eventId,
        UUID departmentId,
        String departmentName,
        String departmentCode,
        UUID deletedBy,
        OffsetDateTime occurredAt
) {
    public static DepartmentDeletedEvent create(
            UUID departmentId, String departmentName, String departmentCode, UUID deletedBy) {
        return new DepartmentDeletedEvent(
                UUID.randomUUID(),
                departmentId,
                departmentName,
                departmentCode,
                deletedBy,
                OffsetDateTime.now()
        );
    }
}
