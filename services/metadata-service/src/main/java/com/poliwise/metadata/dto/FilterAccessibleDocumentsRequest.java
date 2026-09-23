package com.poliwise.metadata.dto;

import java.util.List;
import java.util.UUID;

/**
 * Request to filter accessible documents for a user.
 */
public record FilterAccessibleDocumentsRequest(
    List<UUID> documentIds,
    UUID userId,
    String role,
    UUID departmentId
) {}
