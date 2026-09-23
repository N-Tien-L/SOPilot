package com.poliwise.metadata.dto;

import com.poliwise.metadata.entity.DocumentMetadata;
import com.poliwise.metadata.enums.AccessLevel;
import com.poliwise.metadata.enums.DocumentStatus;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record DocumentMetadataResponse(
        UUID id,
        UUID documentId,
        String title,
        String description,
        String documentType,
        UUID categoryId,
        String categoryName,
        UUID departmentId,
        AccessLevel accessLevel,
        LocalDate effectiveDate,
        LocalDate expiryDate,
        DocumentStatus status,
        Integer currentVersion,
        UUID createdBy,
        String createdByUsername,
        UUID updatedBy,
        String updatedByUsername,
        UUID publishedBy,
        OffsetDateTime publishedAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        List<TagResponse> tags,
        List<AccessRuleResponse> accessRules
) {
    public static DocumentMetadataResponse from(DocumentMetadata dm, String categoryName,
                                                 String createdByUsername, String updatedByUsername,
                                                 List<TagResponse> tags, List<AccessRuleResponse> rules) {
        return new DocumentMetadataResponse(
                dm.getId(), dm.getDocumentId(), dm.getTitle(), dm.getDescription(),
                dm.getDocumentType(), dm.getCategoryId(), categoryName,
                dm.getDepartmentId(), dm.getAccessLevel(), dm.getEffectiveDate(),
                dm.getExpiryDate(), dm.getStatus(), dm.getCurrentVersion(),
                dm.getCreatedBy(), createdByUsername, dm.getUpdatedBy(), updatedByUsername,
                dm.getPublishedBy(), dm.getPublishedAt(),
                dm.getCreatedAt(), dm.getUpdatedAt(),
                tags, rules
        );
    }
}