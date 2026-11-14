package com.sopilot.core.document;

import com.sopilot.core.document.DocumentRepository.CategoryRef;
import com.sopilot.core.document.DocumentRepository.DepartmentRef;
import com.sopilot.core.document.DocumentRepository.DocumentDetail;
import com.sopilot.core.document.DocumentRepository.FieldSources;
import com.sopilot.core.document.DocumentRepository.Suggestions;
import com.sopilot.core.document.DocumentRepository.VersionRow;
import com.sopilot.core.document.DocumentRepository.VersionWithUploader;
import com.sopilot.core.security.AuthPrincipal;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * The {@code Document} object of TECH §5.5.
 * {@code departments}, {@code ownerDepartment}, {@code fieldSources}, {@code suggestions} (stored suggestions that
 * were not applied: the title and a new category name), and {@code latestVersion.failure*} are for
 * OWNER/ADMIN and for the publisher responsible for the document (TECH §15.3); other readers get {@code null}.
 */
public record DocumentView(UUID id, String title, String description,
                           CategoryRef category, List<String> tags,
                           String language, String visibility,
                           List<DepartmentRef> departments,
                           DepartmentRef ownerDepartment,
                           String status, boolean answerable,
                           LatestVersion latestVersion,
                           CurrentVersion currentVersion,
                           FieldSources fieldSources,
                           Suggestions suggestions,
                           Creator createdBy, OffsetDateTime createdAt,
                           OffsetDateTime updatedAt) {

    public record LatestVersion(UUID id, int versionNo, String status, String failureCode, String failureMessage) {
    }

    public record CurrentVersion(UUID id, int versionNo, String originalName, String fileType, long sizeBytes,
                                 Integer pageCount, String docCode, String revisionLabel, LocalDate effectiveDate,
                                 List<String> warningCodes) {
    }

    public record Creator(UUID id, String displayName) {
    }

    /** Administrative fields for managers only; the service passes {@code adminView} for responsible publishers. */
    static DocumentView of(DocumentDetail d, AuthPrincipal viewer) {
        return of(d, viewer, viewer.isManager());
    }

    static DocumentView of(DocumentDetail d, AuthPrincipal viewer, boolean manager) {
        VersionRow latest = d.latest();
        DepartmentRef owner = null;
        if (manager && d.ownerDepartmentId() != null && d.departments() != null) {
            owner = d.departments().stream().filter(x -> x.id().equals(d.ownerDepartmentId())).findFirst()
                    .orElse(new DepartmentRef(d.ownerDepartmentId(), null));
        }
        return new DocumentView(d.id(), d.title(), d.description(),
                d.category(), d.tags() == null ? List.of() : d.tags(),
                d.language(), d.visibility(),
                manager ? d.departments() : null,
                owner,
                latest.status(), d.current() != null,
                new LatestVersion(latest.id(), latest.versionNo(), latest.status(),
                        manager ? latest.failureCode() : null, manager ? latest.failureMessage() : null),
                d.current() == null ? null : currentOf(d.current()),
                manager ? d.fieldSources() : null,
                manager ? d.suggestions() : null,
                new Creator(d.createdBy(), d.creatorName()), d.createdAt(), d.updatedAt());
    }

    private static CurrentVersion currentOf(VersionRow v) {
        return new CurrentVersion(v.id(), v.versionNo(), v.originalName(), v.fileType(), v.sizeBytes(),
                v.pageCount(), v.docCode(), v.revisionLabel(), v.effectiveDate(), List.of(v.warningCodes()));
    }

    /**
     * One row of {@code GET /documents/{id}/versions} (OWNER/ADMIN and the responsible publisher).
     * {@code uploadedBy} and {@code uploadedAt} come from {@code document_versions.uploaded_by} and {@code created_at}.
     */
    public record VersionHistory(UUID id, int versionNo, String status, String failureCode, String failureMessage,
                                 String originalName, String fileType, long sizeBytes, Integer pageCount,
                                 int attempt, Creator uploadedBy, OffsetDateTime uploadedAt) {
        static VersionHistory of(VersionWithUploader row) {
            VersionRow v = row.version();
            return new VersionHistory(v.id(), v.versionNo(), v.status(), v.failureCode(), v.failureMessage(),
                    v.originalName(), v.fileType(), v.sizeBytes(), v.pageCount(), v.attempt(),
                    new Creator(v.uploadedBy(), row.uploaderName()), v.createdAt());
        }
    }
}
