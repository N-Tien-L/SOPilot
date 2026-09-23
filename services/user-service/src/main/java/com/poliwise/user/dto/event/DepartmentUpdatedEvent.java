package com.poliwise.user.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DepartmentUpdatedEvent(
        UUID eventId,
        UUID departmentId,
        String departmentName,
        String departmentCode,
        UUID updatedBy,
        OffsetDateTime occurredAt
) {
    public static DepartmentUpdatedEvent create(
            UUID departmentId, String departmentName, String departmentCode, UUID updatedBy) {
        return new DepartmentUpdatedEvent(
                UUID.randomUUID(),
                departmentId,
                departmentName,
                departmentCode,
                updatedBy,
                OffsetDateTime.now()
        );
    }
}
