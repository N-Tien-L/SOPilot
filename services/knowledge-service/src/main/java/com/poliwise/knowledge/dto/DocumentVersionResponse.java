package com.poliwise.knowledge.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DocumentVersionResponse(
        UUID id,
        UUID documentId,
        Integer versionNumber,
        String fileKey,
        Long fileSizeBytes,
        String changelog,
        UUID createdBy,
        OffsetDateTime createdAt
) {}