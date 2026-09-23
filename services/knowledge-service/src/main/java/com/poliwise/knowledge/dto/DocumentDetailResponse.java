package com.poliwise.knowledge.dto;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record DocumentDetailResponse(
        UUID id,
        String originalFilename,
        String fileType,
        Long fileSizeBytes,
        String mimeType,
        String status,
        Integer currentVersion,
        Integer pageCount,
        Integer wordCount,
        String language,
        String bucketName,
        String fileKey,
        String downloadUrl,
        UUID uploadedBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        List<DocumentVersionResponse> versions
) {}
