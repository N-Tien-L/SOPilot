package com.poliwise.knowledge.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;

/**
 * Response from ingestion-service POST /api/v1/metadata/suggest.
 * Contains AI-suggested metadata for user review/confirmation.
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record MetadataSuggestionResponse(
        String categorySlug,
        String title,
        String description,
        List<String> tags,
        String language,
        boolean isPolicy
) {}
