package com.poliwise.knowledge.dto;

import java.util.UUID;

/**
 * Response for /check-duplicate endpoint.
 * Used for pre-confirm duplicate detection in the upload flow.
 */
public record DuplicateCheckResponse(
    boolean isDuplicate,
    String action,
    DocumentDuplicateInfo existingDocument,
    Double similarity,
    String detectionMethod
) {
    public static DuplicateCheckResponse notDuplicate() {
        return new DuplicateCheckResponse(false, null, null, null, null);
    }

    public static DuplicateCheckResponse duplicate(BlockAction blockAction, DocumentDuplicateInfo existing, String method) {
        return new DuplicateCheckResponse(true, blockAction.name(), existing, null, method);
    }

    public enum BlockAction {
        BLOCK,
        SUGGEST_VERSION
    }
}
