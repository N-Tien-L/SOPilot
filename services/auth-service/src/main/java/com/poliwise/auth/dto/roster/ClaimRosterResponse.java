package com.poliwise.auth.dto.roster;

import com.poliwise.auth.enums.UserRole;
import java.util.UUID;

/**
 * Response payload received from user-service after successful JIT claim.
 */
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
