package com.poliwise.feedback.dto.response;

import com.poliwise.feedback.enums.AuditAction;
import com.poliwise.feedback.enums.ResourceType;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record AuditLogResponse(
        UUID id,
        UUID userId,
        String username,
        String userRole,
        AuditAction action,
        ResourceType resourceType,
        UUID resourceId,
        String resourceName,
        String ipAddress,
        Instant createdAt,
        Map<String, Object> oldValue,
        Map<String, Object> newValue,
        String[] changedFields
) {}
