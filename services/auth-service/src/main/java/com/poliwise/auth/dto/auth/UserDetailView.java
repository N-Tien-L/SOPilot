package com.poliwise.auth.dto.auth;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserDetailView(
        UUID id,
        String username,
        String email,
        String fullName,
        String role,
        String status,
        UUID departmentId,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        UUID createdBy,
        int failedLoginAttempts,
        OffsetDateTime passwordChangedAt,
        boolean mustChangePassword
) {}
