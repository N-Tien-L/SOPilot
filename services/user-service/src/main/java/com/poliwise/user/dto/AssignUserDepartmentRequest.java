package com.poliwise.user.dto;

import jakarta.validation.constraints.NotNull;
import java.util.UUID;

/**
 * DTO gán/phân công phòng ban cho người dùng.
 */
public record AssignUserDepartmentRequest(
        @NotNull(message = "userId là bắt buộc")
        UUID userId,

        @NotNull(message = "departmentId là bắt buộc")
        UUID departmentId
) {}
