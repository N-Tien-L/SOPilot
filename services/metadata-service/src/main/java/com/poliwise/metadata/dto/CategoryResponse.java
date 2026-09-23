package com.poliwise.metadata.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record CategoryResponse(
        UUID id,
        String name,
        String slug,
        String description,
        UUID parentId,
        String icon,
        Integer displayOrder,
        Boolean isActive,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {}