package com.poliwise.knowledge.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Response containing the latest version metadata and a presigned download URL.
 * Used by the frontend to preview the newest version during conflict resolution.
 */
public record FetchLatestVersionResponse(
    UUID documentId,
    UUID versionId,
    int versionNumber,
    String changelog,
    UUID createdBy,
    String createdByUsername,
    OffsetDateTime createdAt,
    long fileSizeBytes,
    String downloadUrl
) {}
