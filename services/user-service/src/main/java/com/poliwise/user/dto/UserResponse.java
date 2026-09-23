package com.poliwise.user.dto;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

public record UserResponse(
        UUID id,
        String username,
        String email,
        UserRole role,
        AccountStatus status,
        UUID departmentId,
        DepartmentInfo department,
        UserProfileInfo profile,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {

    public record DepartmentInfo(UUID id, String name, String code) {}

    public record UserProfileInfo(
            UUID id,
            String fullName,
            String phone,
            String position,
            String avatarUrl,
            String bio,
            LocalDate dateOfBirth,
            String employeeCode,
            LocalDate joinedDate
    ) {}
}
