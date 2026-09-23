package com.poliwise.metadata.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record AccessRuleResponse(
        UUID id,
        UUID documentMetadataId,
        String targetType,
        String targetRole,
        UUID targetDepartmentId,
        String targetDepartmentName,
        UUID targetUserId,
        String targetUserName,
        String permission,
        UUID createdBy,
        OffsetDateTime createdAt
) {}