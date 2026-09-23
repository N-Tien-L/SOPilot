package com.poliwise.metadata.dto;

import java.util.UUID;

/**
 * Response indicating if a user has access to a document.
 */
public record DocumentAccessCheckResponse(
    UUID documentId,
    boolean hasAccess,
    String reason
) {}
