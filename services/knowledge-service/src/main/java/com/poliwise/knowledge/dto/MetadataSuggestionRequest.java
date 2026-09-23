package com.poliwise.knowledge.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;

/**
 * Request payload sent to ingestion-service POST /api/v1/metadata/suggest.
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record MetadataSuggestionRequest(
        String fileKey,
        String bucketName,
        List<String> availableCategories,
        List<String> topTags
) {}
