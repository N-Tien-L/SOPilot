package com.poliwise.knowledge.dto;

import jakarta.validation.constraints.NotBlank;

public record ProcessDocumentRequest(
        @NotBlank(message = "Changelog is required")
        String changelog,

        Boolean forceReprocess
) {}