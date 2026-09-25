package com.poliwise.user.dto.roster;

import java.util.List;
import java.util.UUID;

public record RosterImportResponse(
        UUID batchId,
        int totalRows,
        int importedCount,
        int failedCount,
        List<RosterRowError> errors
) {
    public static RosterImportResponse of(
            UUID batchId,
            int totalRows,
            int importedCount,
            int failedCount,
            List<RosterRowError> errors) {
        return new RosterImportResponse(batchId, totalRows, importedCount, failedCount, errors != null ? errors : List.of());
    }
}
