package com.poliwise.metadata.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.UUID;

public record UpdateDocumentMetadataRequest(
        @NotBlank(message = "title is required") @Size(max = 255, message = "title must be at most 255 characters") String title,
        @Size(max = 2000, message = "description must be at most 2000 characters") String description,
        @Size(max = 100, message = "documentType must be at most 100 characters") String documentType,
        UUID categoryId,
        UUID departmentId,
        com.poliwise.metadata.enums.AccessLevel accessLevel,
        java.time.LocalDate effectiveDate,
        java.time.LocalDate expiryDate
) {}