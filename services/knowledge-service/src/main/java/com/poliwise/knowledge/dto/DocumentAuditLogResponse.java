package com.poliwise.knowledge.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DocumentAuditLogResponse(
        UUID id,
        UUID documentId,
        String action,
        UUID actorId,
        String actorUsername,
        Object oldValues,
        Object newValues,
        String ipAddress,
        OffsetDateTime createdAt
) {}
