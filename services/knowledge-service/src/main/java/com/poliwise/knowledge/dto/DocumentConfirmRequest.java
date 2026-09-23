package com.poliwise.knowledge.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * Request payload from the UI when the user confirms AI-suggested (or manually entered) metadata.
 * This triggers metadata persistence in metadata-service (Phase 1 only — no ingestion triggered).
 */
public record DocumentConfirmRequest(
        @NotBlank(message = "title is required")
        @Size(max = 255, message = "title must be at most 255 characters")
        String title,

        @Size(max = 2000, message = "description must be at most 2000 characters")
        String description,

        String categorySlug,

        List<String> tags,

        String language,

        Boolean isPolicy,

        String fileChecksum
) {}
