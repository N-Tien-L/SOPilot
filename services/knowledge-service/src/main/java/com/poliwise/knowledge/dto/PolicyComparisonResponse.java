package com.poliwise.knowledge.dto;

import java.util.List;
import java.util.Map;

public record PolicyComparisonResponse(
        String document1Id,
        String document2Id,
        String document1Title,
        String document2Title,
        List<DiffSection> addedSections,
        List<DiffSection> removedSections,
        List<DiffSection> modifiedSections,
        int totalChanges
) {

    public record DiffSection(
            String sectionTitle,
            String oldContent,
            String newContent,
            String changeType // ADDED, REMOVED, MODIFIED
    ) {}
}