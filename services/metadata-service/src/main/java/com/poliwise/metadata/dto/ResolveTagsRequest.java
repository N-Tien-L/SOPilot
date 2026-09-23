package com.poliwise.metadata.dto;

import jakarta.validation.constraints.NotEmpty;
import java.util.List;

public record ResolveTagsRequest(
    @NotEmpty(message = "Tag names list cannot be empty")
    List<String> tagNames
) {}
