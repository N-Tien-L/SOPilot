package com.poliwise.knowledge.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Summary info about the existing duplicate document.
 */
public record DocumentDuplicateInfo(
    UUID documentId,
    String originalFilename,
    Long fileSizeBytes,
    OffsetDateTime createdAt,
    String title,
    String categorySlug,
    String status,
    String fileChecksum
) {}
