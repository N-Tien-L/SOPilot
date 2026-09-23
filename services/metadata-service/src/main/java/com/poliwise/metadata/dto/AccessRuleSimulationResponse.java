package com.poliwise.metadata.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record AccessRuleSimulationResponse(
        UUID userId,
        String username,
        String fullName,
        String role,
        UUID departmentId,
        String departmentName,
        boolean hasAccess,
        String reason,
        OffsetDateTime simulatedAt
) {}
