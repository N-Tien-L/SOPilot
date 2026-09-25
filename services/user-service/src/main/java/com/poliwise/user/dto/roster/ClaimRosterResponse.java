package com.poliwise.user.dto.roster;

import com.poliwise.user.enums.UserRole;

import java.util.UUID;

public record ClaimRosterResponse(
        UUID userId,
        String username,
        String email,
        String fullName,
        UserRole role,
        UUID departmentId,
        String departmentName,
        String departmentCode
) {}
