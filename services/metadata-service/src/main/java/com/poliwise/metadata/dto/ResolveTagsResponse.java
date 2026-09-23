package com.poliwise.metadata.dto;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ResolveTagsResponse(
    Map<String, UUID> resolvedTags,
    List<UUID> tagIds
) {}
