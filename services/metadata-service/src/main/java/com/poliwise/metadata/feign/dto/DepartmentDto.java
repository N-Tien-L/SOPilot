package com.poliwise.metadata.feign.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DepartmentDto(
        UUID id,
        String name,
        String code,
        ParentDepartmentInfo parent,
        Boolean isActive,
        int userCount,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public record ParentDepartmentInfo(UUID id, String name, String code) {}
}
