package com.poliwise.user.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DepartmentCreatedEvent(
        UUID eventId,
        UUID departmentId,
        String departmentName,
        String departmentCode,
        UUID parentId,
        UUID createdBy,
        OffsetDateTime occurredAt
) {
    public static DepartmentCreatedEvent create(
            UUID departmentId, String departmentName, String departmentCode,
            UUID parentId, UUID createdBy) {
        return new DepartmentCreatedEvent(
                UUID.randomUUID(),
                departmentId,
                departmentName,
                departmentCode,
                parentId,
                createdBy,
                OffsetDateTime.now()
        );
    }
}
