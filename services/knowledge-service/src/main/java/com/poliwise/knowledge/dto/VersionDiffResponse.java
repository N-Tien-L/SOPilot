package com.poliwise.knowledge.dto;

import java.util.List;
import java.util.UUID;

public record VersionDiffResponse(
    UUID documentId,
    int baseVersion,
    int compareVersion,
    String baseContent,
    String compareContent,
    List<DiffLine> lines,
    int additions,
    int deletions
) {
    public record DiffLine(
        DiffType type,
        int lineNumber,
        String content
    ) {}

    public enum DiffType {
        UNCHANGED, ADDED, DELETED
    }
}
