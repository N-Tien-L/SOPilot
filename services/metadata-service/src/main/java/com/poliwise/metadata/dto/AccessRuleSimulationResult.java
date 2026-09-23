package com.poliwise.metadata.dto;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record AccessRuleSimulationResult(
        UUID documentId,
        UUID metadataId,
        int totalCompanyUsers,
        int usersWithAccess,
        int usersWithoutAccess,
        List<AccessRuleSimulationResponse> grantedUsers,
        List<AccessRuleSimulationResponse> deniedUsers,
        OffsetDateTime simulatedAt
) {}
