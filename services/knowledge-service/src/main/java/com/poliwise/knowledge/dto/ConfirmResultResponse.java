package com.poliwise.knowledge.dto;

/**
 * Extended response from /confirm endpoint when sync processing is used.
 */
public record ConfirmResultResponse(
    String status,
    Integer chunkCount,
    DocumentDuplicateInfo nearDuplicateOf,
    Double similarity
) {
    public static ConfirmResultResponse ready(int chunkCount) {
        return new ConfirmResultResponse("READY", chunkCount, null, null);
    }

    public static ConfirmResultResponse nearDuplicate(DocumentDuplicateInfo existing, double similarity) {
        return new ConfirmResultResponse("NEAR_DUPLICATE", null, existing, similarity);
    }

    public static ConfirmResultResponse duplicate(DocumentDuplicateInfo existing) {
        return new ConfirmResultResponse("DUPLICATE", null, existing, null);
    }
}
