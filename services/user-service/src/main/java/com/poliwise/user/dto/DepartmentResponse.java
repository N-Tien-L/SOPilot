package com.poliwise.user.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * DTO phản hồi thông tin phòng ban.
 */
public record DepartmentResponse(
        UUID id,
        String name,
        String code,
        String description,
        ParentDepartmentInfo parent,
        Boolean isActive,
        int userCount,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {

    public record ParentDepartmentInfo(UUID id, String name, String code) {}

    /**
     * Compact info dùng trong danh sách phòng ban con.
     */
    public record DepartmentInfo(UUID id, String name, String code) {}

    /**
     * Tree info cho hierarchical display.
     */
    public record DepartmentTreeInfo(
            UUID id,
            String name,
            String code,
            Boolean isActive,
            java.util.List<DepartmentTreeInfo> children
    ) {}
}
