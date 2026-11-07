package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.document.DocumentRepository.DocumentHead;
import com.sopilot.core.document.DocumentRepository.VersionRow;
import com.sopilot.core.storage.StorageClient;
import com.sopilot.core.tenancy.TenantTx;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Applies ai-service status callbacks to a version (TECH-V2-core-api §8.2). Valid moves:
 * {@code UPLOADED → PROCESSING → READY | FAILED}, {@code FAILED → PROCESSING} (ai-service's own retry),
 * and {@code FAILED → UPLOADED} which only {@code POST /retry} performs. A callback carrying an older
 * {@code attempt} is ignored with success. {@code READY} switches the document to the new version and
 * supersedes every older one, FAILED ones included; a failing new version leaves the old one serving.
 */
@Service
public class VersionStatusService {

    private static final Set<String> CAN_START = Set.of("UPLOADED", "FAILED");
    private static final Set<String> CAN_FINISH = Set.of("UPLOADED", "PROCESSING");

    private final DocumentRepository docs;
    private final StorageClient storage;
    private final TenantTx tenant;

    public VersionStatusService(DocumentRepository docs, StorageClient storage, TenantTx tenant) {
        this.docs = docs;
        this.storage = storage;
        this.tenant = tenant;
    }

    /** What ai-service reports; every field except {@code workspaceId} and {@code status} is optional. */
    public record Update(UUID workspaceId, String status, int attempt, Integer pageCount, String detectedLanguage,
                         Integer chunkCount, Embedding embedding, Extracted extracted, List<String> warningCodes,
                         String failureCode) {
    }

    public record Embedding(String provider, String model, String revision, Integer dim) {
    }

    public record Extracted(String docCode, String revisionLabel, String effectiveDate, String approvedBy) {
    }

    /** ai-service extracts dates from free text; anything that is not an ISO date is dropped, never a 4xx. */
    static LocalDate parseDate(String value) {
        try {
            return value == null ? null : LocalDate.parse(value.strip());
        } catch (java.time.format.DateTimeParseException e) {
            return null;
        }
    }

    /** @return false when the callback was stale (older attempt) and changed nothing */
    public boolean apply(UUID documentId, UUID versionId, Update update) {
        if (update.workspaceId() == null || update.status() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
        }
        UUID wid = update.workspaceId();
        return tenant.run(wid, null, () -> {
            DocumentHead head = docs.lockDocument(wid, documentId).orElseThrow(VersionStatusService::invalid);
            VersionRow version = docs.findVersionForUpdate(wid, documentId, versionId)
                    .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Version not found."));
            if (update.attempt() < version.attempt()) {
                return false;
            }
            switch (update.status()) {
                case "PROCESSING" -> processing(version);
                case "READY" -> ready(wid, head, version, update);
                case "FAILED" -> failed(version, update);
                default -> throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
            }
            return true;
        });
    }

    private void processing(VersionRow version) {
        if (CAN_START.contains(version.status())) {
            docs.setStatus(version.id(), "PROCESSING");
        } else if (!"PROCESSING".equals(version.status())) {
            throw invalid();
        }
    }

    private void ready(UUID wid, DocumentHead head, VersionRow version, Update u) {
        if ("READY".equals(version.status())) {
            return;
        }
        if (!CAN_FINISH.contains(version.status())) {
            throw invalid();
        }
        if (head.currentVersionId() != null) {
            VersionRow current = docs.findVersion(wid, version.documentId(), head.currentVersionId()).orElse(null);
            if (current != null && current.versionNo() > version.versionNo()) {
                throw invalid();
            }
        }
        Embedding embedding = u.embedding();
        Extracted extracted = u.extracted();
        docs.markReady(version.id(), u.pageCount(), u.detectedLanguage(), u.chunkCount(),
                embedding == null ? null : embedding.model(), embedding == null ? null : embedding.revision(),
                extracted == null ? null : extracted.docCode(), extracted == null ? null : extracted.revisionLabel(),
                extracted == null ? null : parseDate(extracted.effectiveDate()),
                u.warningCodes() == null ? new String[0] : u.warningCodes().toArray(String[]::new));
        List<String> supersededKeys = docs.activate(version.documentId(), version.id(), version.versionNo(),
                u.detectedLanguage());
        // The previous version's file is not needed any more (TECH §11 Q4); a failed delete is best-effort.
        AfterCommit.run("delete superseded objects", () -> supersededKeys.forEach(storage::delete));
    }

    private void failed(VersionRow version, Update u) {
        if ("FAILED".equals(version.status())) {
            return;
        }
        if (!CAN_FINISH.contains(version.status())) {
            throw invalid();
        }
        String code = FailureMessages.normalize(u.failureCode());
        docs.markFailed(version.id(), code, FailureMessages.forCode(code));
    }

    private static ApiException invalid() {
        return new ApiException(HttpStatus.CONFLICT, "INVALID_TRANSITION", "The version cannot move to that status.");
    }
}
