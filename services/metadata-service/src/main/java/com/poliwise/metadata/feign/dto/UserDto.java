package com.poliwise.metadata.feign.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserDto(
        UUID id,
        String username,
        String email,
        String role,
        String accountStatus,
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
            String dateOfBirth,
            String employeeCode,
            String joinedDate
    ) {}

    public String fullName() {
        return profile != null ? profile.fullName() : null;
    }

    public UUID departmentId() {
        return department != null ? department.id() : null;
    }

    public String departmentName() {
        return department != null ? department.name() : null;
    }
}
