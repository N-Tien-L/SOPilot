package com.poliwise.metadata.dto;

import com.poliwise.metadata.enums.AccessLevel;
import com.poliwise.metadata.enums.DocumentStatus;
import com.poliwise.metadata.enums.RulePermission;
import com.poliwise.metadata.enums.RuleTargetType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public record CreateDocumentMetadataRequest(
        @NotNull(message = "documentId is required") UUID documentId,
        @NotBlank(message = "title is required") @Size(max = 255, message = "title must be at most 255 characters") String title,
        @Size(max = 2000, message = "description must be at most 2000 characters") String description,
        @Size(max = 100, message = "documentType must be at most 100 characters") String documentType,
        UUID categoryId,
        UUID departmentId,
        @NotNull(message = "accessLevel is required") AccessLevel accessLevel,
        LocalDate effectiveDate,
        LocalDate expiryDate,
        List<UUID> tagIds,
        List<AccessRuleDto> accessRules
) {
    public record AccessRuleDto(
            RuleTargetType targetType,
            String targetRole,
            UUID targetDepartmentId,
            UUID targetUserId,
            RulePermission permission
    ) {}
}