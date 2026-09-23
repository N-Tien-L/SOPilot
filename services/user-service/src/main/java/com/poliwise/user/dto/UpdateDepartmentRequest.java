package com.poliwise.user.dto;

import jakarta.validation.constraints.Size;

import java.util.UUID;

/**
 * DTO cập nhật phòng ban.
 */
public record UpdateDepartmentRequest(
        @Size(max = 100, message = "Tên phòng ban không được vượt quá 100 ký tự")
        String name,

        String description,

        UUID parentId,

        Boolean isActive
) {}
