package com.poliwise.feedback.feign.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DepartmentListResponse(
        UUID id,
        String name,
        String code,
        String description,
        ParentDepartmentInfo parent,
        Boolean isActive,
        Integer memberCount,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public record ParentDepartmentInfo(
            UUID id,
            String name,
            String code
    ) {}
}
