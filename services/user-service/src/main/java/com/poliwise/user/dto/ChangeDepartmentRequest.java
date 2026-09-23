package com.poliwise.user.dto;

import jakarta.validation.constraints.NotNull;

import java.util.UUID;

public record ChangeDepartmentRequest(
        @NotNull(message = "Department ID is required")
        UUID departmentId
) {}
