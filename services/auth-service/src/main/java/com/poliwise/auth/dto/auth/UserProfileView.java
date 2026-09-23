package com.poliwise.auth.dto.auth;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserProfileView(
        UUID id,
        String username,
        String email,
        String fullName,
        String role,
        String status,
        UUID departmentId,
        String departmentName,
        OffsetDateTime createdAt,
        OffsetDateTime passwordChangedAt,
        boolean mustChangePassword
) {}
