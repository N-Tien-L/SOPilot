package com.poliwise.metadata.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.UUID;

public record UpdateAccessRuleRequest(
        @NotBlank(message = "targetType is required") String targetType,
        String targetRole,
        UUID targetDepartmentId,
        UUID targetUserId,
        @NotBlank(message = "permission is required") @Size(max = 50, message = "permission must be at most 50 characters") String permission
) {}
