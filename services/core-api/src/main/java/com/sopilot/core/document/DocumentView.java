package com.sopilot.core.document;

import com.sopilot.core.document.DocumentRepository.DocumentDetail;
import com.sopilot.core.document.DocumentRepository.VersionRow;
import com.sopilot.core.security.AuthPrincipal;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * The {@code Document} object of TECH §5.5. {@code latestVersion.failure*} is for OWNER/ADMIN only.
 * Category, tags, departments, field sources and suggestions arrive with V2-24/V2-25.
 */
public record DocumentView(UUID id, String title, String description, String language, String visibility,
                           String status, boolean answerable, LatestVersion latestVersion,
                           CurrentVersion currentVersion, Creator createdBy, OffsetDateTime createdAt,
                           OffsetDateTime updatedAt) {

    public record LatestVersion(UUID id, int versionNo, String status, String failureCode, String failureMessage) {
    }

    public record CurrentVersion(UUID id, int versionNo, String originalName, String fileType, long sizeBytes,
                                 Integer pageCount, String docCode, String revisionLabel, LocalDate effectiveDate,
                                 List<String> warningCodes) {
    }

    public record Creator(UUID id, String displayName) {
    }

    static DocumentView of(DocumentDetail d, AuthPrincipal viewer) {
        VersionRow latest = d.latest();
        boolean manager = viewer.isManager();
        return new DocumentView(d.id(), d.title(), d.description(), d.language(), d.visibility(),
                latest.status(), d.current() != null,
                new LatestVersion(latest.id(), latest.versionNo(), latest.status(),
                        manager ? latest.failureCode() : null, manager ? latest.failureMessage() : null),
                d.current() == null ? null : currentOf(d.current()),
                new Creator(d.createdBy(), d.creatorName()), d.createdAt(), d.updatedAt());
    }

    private static CurrentVersion currentOf(VersionRow v) {
        return new CurrentVersion(v.id(), v.versionNo(), v.originalName(), v.fileType(), v.sizeBytes(),
                v.pageCount(), v.docCode(), v.revisionLabel(), v.effectiveDate(), List.of(v.warningCodes()));
    }

    /** One row of {@code GET /documents/{id}/versions} (OWNER/ADMIN). */
    public record VersionHistory(UUID id, int versionNo, String status, String failureCode, String failureMessage,
                                 String originalName, String fileType, long sizeBytes, Integer pageCount,
                                 int attempt, OffsetDateTime createdAt) {
        static VersionHistory of(VersionRow v) {
            return new VersionHistory(v.id(), v.versionNo(), v.status(), v.failureCode(), v.failureMessage(),
                    v.originalName(), v.fileType(), v.sizeBytes(), v.pageCount(), v.attempt(), v.createdAt());
        }
    }
}
