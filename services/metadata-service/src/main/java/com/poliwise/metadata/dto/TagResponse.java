package com.poliwise.metadata.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record TagResponse(
        UUID id,
        String name,
        String slug,
        String color,
        Integer usageCount,
        OffsetDateTime createdAt
) {}