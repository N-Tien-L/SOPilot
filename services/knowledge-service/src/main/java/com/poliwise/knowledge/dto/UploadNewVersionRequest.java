package com.poliwise.knowledge.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record UploadNewVersionRequest(
        @NotBlank(message = "Changelog is required")
        String changelog,

        String language
) {}
