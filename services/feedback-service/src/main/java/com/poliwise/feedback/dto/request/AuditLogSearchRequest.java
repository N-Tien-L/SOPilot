package com.poliwise.feedback.dto.request;

import com.poliwise.feedback.enums.AuditAction;
import com.poliwise.feedback.enums.ResourceType;

import java.time.LocalDateTime;
import java.util.UUID;

public record AuditLogSearchRequest(
        AuditAction action,
        UUID userId,
        ResourceType resourceType,
        UUID resourceId,
        LocalDateTime fromDate,
        LocalDateTime toDate,
        String search
) {}
