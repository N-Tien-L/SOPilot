package com.poliwise.metadata.dto;

import java.util.List;
import java.util.UUID;

/**
 * Response containing accessible document IDs for a user.
 */
public record FilterAccessibleDocumentsResponse(
    List<UUID> accessibleDocumentIds,
    int totalRequested,
    int accessibleCount
) {}
