package com.poliwise.knowledge.dto;

import java.util.UUID;

public record DeleteVersionRequest(
    UUID documentId,
    Integer versionNumber,
    String reason
) {}
