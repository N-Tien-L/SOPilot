package com.sopilot.core.document;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.category.CategoryRepository;
import com.sopilot.core.category.CategoryRepository.Category;
import com.sopilot.core.category.CategoryRepository.CategoryStatus;
import com.sopilot.core.category.CategoryService;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.Cursor;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.config.QuotaProperties;
import com.sopilot.core.department.DepartmentRepository;
import com.sopilot.core.department.DepartmentRepository.Department;
import com.sopilot.core.department.DepartmentRepository.DepartmentStatus;
import com.sopilot.core.document.DocumentRepository.DocumentDetail;
import com.sopilot.core.document.DocumentRepository.DocumentHead;
import com.sopilot.core.document.DocumentRepository.Duplicate;
import com.sopilot.core.document.DocumentRepository.MetaSources;
import com.sopilot.core.document.DocumentRepository.Usage;
import com.sopilot.core.document.DocumentRepository.VersionRow;
import com.sopilot.core.document.UploadValidator.Validated;
import com.sopilot.core.outbox.OutboxDispatcher;
import com.sopilot.core.outbox.OutboxEvent;
import com.sopilot.core.outbox.OutboxService;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.storage.StorageClient;
import com.sopilot.core.tag.TagService;
import com.sopilot.core.tenancy.TenantTx;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Documents, versions, the document quota and the upload/replace/retry/delete lifecycle
 * (FR-06, FR-07, FR-09; TECH-V2-core-api §2.2, §3.3, §5.5). Everything here runs in one tenant
 * transaction; the outbox row and the audit entry commit with the change they describe.
 *
 * <p>Order inside an upload: checks and rows first, the S3 {@code PUT} last, then commit. A conflict
 * (duplicate, quota, version in progress) therefore never touches storage, and the only way to leave an
 * orphan object is a commit that fails after the {@code PUT}, which {@code StorageJanitor} removes.
 * Locks are always taken in the order document row, then SHA-256, then workspace quota.
 */
@Service
public class DocumentService {

    private static final Logger log = LoggerFactory.getLogger(DocumentService.class);
    private static final Duration DOWNLOAD_TTL = Duration.ofMinutes(5);
    private static final Set<String> IN_PROGRESS = Set.of("UPLOADED", "PROCESSING");
    private static final Set<String> PATCHABLE = Set.of("title", "description", "language", "categoryId", "tags");

    private final DocumentRepository docs;
    private final CategoryRepository categories;
    private final DepartmentRepository departments;
    private final TagService tagService;
    private final StorageClient storage;
    private final OutboxService outbox;
    private final OutboxDispatcher outboxDispatcher;
    private final AuditService audit;
    private final TenantTx tenant;
    private final QuotaProperties quota;

    public DocumentService(DocumentRepository docs, CategoryRepository categories,
                           DepartmentRepository departments, TagService tagService,
                           StorageClient storage, OutboxService outbox,
                           OutboxDispatcher outboxDispatcher, AuditService audit,
                           TenantTx tenant, QuotaProperties quota) {
        this.docs = docs;
        this.categories = categories;
        this.departments = departments;
        this.tagService = tagService;
        this.storage = storage;
        this.outbox = outbox;
        this.outboxDispatcher = outboxDispatcher;
        this.audit = audit;
        this.tenant = tenant;
        this.quota = quota;
    }

    /** {@code created} is false when a repeated send of the version already in progress was recognised. */
    public record UploadResult(DocumentView document, boolean created) {
    }

    public record VisibilityResponse(String accessSync) {
    }

    // ---- upload ---------------------------------------------------------------------------------

    public UploadResult upload(AuthPrincipal principal, String filename, byte[] content, String visibility) {
        return upload(principal, filename, content, visibility, null, null, null, null);
    }

    public UploadResult upload(AuthPrincipal principal, String filename, byte[] content, String visibility,
                               List<UUID> departmentIds, UUID categoryId, List<String> tags, String requestedTitle) {
        principal.requireManager();
        String effectiveVisibility = (visibility == null || visibility.isBlank()) ? "WORKSPACE" : visibility.strip();
        if (!"WORKSPACE".equals(effectiveVisibility) && !"DEPARTMENTS".equals(effectiveVisibility)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Visibility must be WORKSPACE or DEPARTMENTS.");
        }
        Validated file = UploadValidator.validate(filename, content);
        String title = requestedTitle != null ? text(requestedTitle, 200, false, "title") : titleFrom(file.originalName());
        String titleSource = requestedTitle != null ? "USER" : "SYSTEM";
        UUID wid = principal.workspaceId();
        return tenant.run(principal, () -> {
            List<UUID> effectiveDepartmentIds = resolveDepartments(wid, effectiveVisibility, departmentIds);

            if (categoryId != null) {
                Category cat = categories.find(wid, categoryId).orElseThrow(CategoryService::notFound);
                if (cat.status() == CategoryStatus.ARCHIVED) {
                    throw new ApiException(HttpStatus.BAD_REQUEST, "CATEGORY_ARCHIVED", "Archived categories cannot be assigned.");
                }
            }

            docs.advisoryLock("sha:" + wid + ":" + file.sha256Hex());
            docs.advisoryLock("quota:" + wid);
            docs.findDuplicate(wid, file.sha256(), null).ifPresent(d -> {
                throw duplicate(d);
            });
            checkQuota(wid, true, file.size());

            UUID documentId = UuidV7.generate();

            UUID versionId = UuidV7.generate();
            String objectKey = objectKey(wid, documentId, versionId);
            String categorySource = categoryId != null ? "USER" : "SYSTEM";
            String tagsSource = (tags != null && !tags.isEmpty()) ? "USER" : "SYSTEM";

            docs.insertDocument(documentId, wid, title, titleSource, versionId, principal.userId(),
                    effectiveVisibility, categoryId, categorySource, tagsSource);
            docs.insertVersion(versionId, wid, documentId, 1, file.originalName(), file.type().mimeType(),
                    file.type().name(), file.size(), file.sha256(), objectKey, principal.userId());

            if ("DEPARTMENTS".equals(effectiveVisibility)) {
                docs.setDocumentDepartments(wid, documentId, effectiveDepartmentIds);
            }
            if (tags != null && !tags.isEmpty()) {
                tagService.assignTags(wid, documentId, tags);
            }

            outbox.enqueue(wid, documentId, OutboxEvent.Type.INGEST_REQUESTED,
                    ingestPayload(wid, documentId, versionId, 1, objectKey, file, 0, title,
                            effectiveVisibility, effectiveDepartmentIds, 1));
            audit.record(principal, "DOCUMENT_UPLOADED", "DOCUMENT", documentId,
                    Map.of("versionId", versionId, "fileType", file.type().name(), "sizeBytes", file.size()));
            putObject(objectKey, content, file.type().mimeType());
            return new UploadResult(view(wid, documentId, principal), true);
        });
    }

    /** The five branches of TECH §3.3, checked in that order inside the document lock. */
    public UploadResult uploadVersion(AuthPrincipal principal, UUID documentId, String filename, byte[] content) {
        principal.requireManager();
        Validated file = UploadValidator.validate(filename, content);
        UUID wid = principal.workspaceId();
        return tenant.run(principal, () -> {
            DocumentHead head = docs.lockDocument(wid, documentId).orElseThrow(DocumentService::notFound);
            docs.advisoryLock("sha:" + wid + ":" + file.sha256Hex());
            docs.advisoryLock("quota:" + wid);

            VersionRow latest = docs.findVersion(wid, documentId, head.latestVersionId()).orElseThrow();
            if (IN_PROGRESS.contains(latest.status())) {
                if (Arrays.equals(latest.sha256(), file.sha256())) {
                    return new UploadResult(view(wid, documentId, principal), false);
                }
                throw new ApiException(HttpStatus.CONFLICT, "VERSION_IN_PROGRESS",
                        "A version of this document is still being processed. Wait for it to finish, then upload again.");
            }
            if (head.currentVersionId() != null) {
                VersionRow current = docs.findVersion(wid, documentId, head.currentVersionId()).orElseThrow();
                if (Arrays.equals(current.sha256(), file.sha256())) {
                    throw new ApiException(HttpStatus.CONFLICT, "DOCUMENT_UNCHANGED",
                            "This file is identical to the current version of the document.");
                }
            }
            docs.findDuplicate(wid, file.sha256(), documentId).ifPresent(d -> {
                throw duplicate(d);
            });
            checkQuota(wid, false, file.size());

            UUID versionId = UuidV7.generate();
            int versionNo = docs.maxVersionNo(wid, documentId) + 1;
            String objectKey = objectKey(wid, documentId, versionId);
            docs.insertVersion(versionId, wid, documentId, versionNo, file.originalName(), file.type().mimeType(),
                    file.type().name(), file.size(), file.sha256(), objectKey, principal.userId());
            docs.setLatestVersion(wid, documentId, versionId);
            outbox.enqueue(wid, documentId, OutboxEvent.Type.INGEST_REQUESTED,
                    ingestPayload(wid, documentId, versionId, versionNo, objectKey, file, 0, head.title(),
                            head.visibility(), docs.departmentIds(wid, documentId), head.accessRevision()));
            audit.record(principal, "DOCUMENT_VERSION_UPLOADED", "DOCUMENT", documentId,
                    Map.of("versionId", versionId, "versionNo", versionNo, "sizeBytes", file.size()));
            putObject(objectKey, content, file.type().mimeType());
            return new UploadResult(view(wid, documentId, principal), true);
        });
    }

    // ---- retry, delete, edit ---------------------------------------------------------------------

    /** Only the newest version, only when {@code FAILED}; a second call finds it {@code UPLOADED} and gets 409. */
    public DocumentView retry(AuthPrincipal principal, UUID documentId) {
        principal.requireManager();
        UUID wid = principal.workspaceId();
        return tenant.run(principal, () -> {
            DocumentHead head = docs.lockDocument(wid, documentId).orElseThrow(DocumentService::notFound);
            VersionRow latest = docs.findVersion(wid, documentId, head.latestVersionId()).orElseThrow();
            if (!"FAILED".equals(latest.status())) {
                throw new ApiException(HttpStatus.CONFLICT, "VERSION_NOT_FAILED",
                        "The latest version of this document is not in a failed state.");
            }
            int attempt = latest.attempt() + 1;
            docs.resetForRetry(wid, latest.id(), attempt);
            Validated file = new Validated(UploadValidator.FileType.valueOf(latest.fileType()), latest.originalName(),
                    latest.sha256(), latest.sizeBytes());
            outbox.enqueue(wid, documentId, OutboxEvent.Type.INGEST_REQUESTED,
                    ingestPayload(wid, documentId, latest.id(), latest.versionNo(), latest.objectKey(), file, attempt,
                            head.title(), head.visibility(), docs.departmentIds(wid, documentId),
                            head.accessRevision()));
            audit.record(principal, "DOCUMENT_RETRY_REQUESTED", "DOCUMENT", documentId,
                    Map.of("versionId", latest.id(), "attempt", attempt));
            return view(wid, documentId, principal);
        });
    }

    /** Soft delete now; the file and rows go once ai-service confirms its cleanup (see {@link DocumentOutboxHooks}). */
    public void delete(AuthPrincipal principal, UUID documentId) {
        principal.requireManager();
        UUID wid = principal.workspaceId();
        tenant.runVoid(wid, principal.userId(), () -> {
            DocumentHead head = docs.lockDocument(wid, documentId).orElseThrow(DocumentService::notFound);
            docs.softDelete(wid, documentId);
            outbox.enqueue(wid, documentId, OutboxEvent.Type.DOCUMENT_DELETED,
                    Map.of("workspaceId", wid, "documentId", documentId));
            audit.record(principal, "DOCUMENT_DELETED", "DOCUMENT", documentId, Map.of("title", head.title()));
        });
    }

    /**
     * Soft-deletes every live document of the caller's workspace, one {@code DOCUMENT_DELETED} event each
     * (workspace delete, TECH §5.2). Joins the caller's tenant transaction when there is one.
     */
    public int deleteAll(AuthPrincipal principal) {
        principal.requireOwner();
        UUID wid = principal.workspaceId();
        return tenant.run(principal, () -> {
            List<UUID> ids = docs.liveDocumentIds(wid);
            for (UUID documentId : ids) {
                DocumentHead head = docs.lockDocument(wid, documentId).orElse(null);
                if (head == null) {
                    continue;
                }
                docs.softDelete(wid, documentId);
                outbox.enqueue(wid, documentId, OutboxEvent.Type.DOCUMENT_DELETED,
                        Map.of("workspaceId", wid, "documentId", documentId));
                audit.record(principal, "DOCUMENT_DELETED", "DOCUMENT", documentId, Map.of("title", head.title()));
            }
            return ids.size();
        });
    }

    /** Title, description, language, categoryId, and tags; never talks to ai-service and never creates an outbox event. */
    public DocumentView update(AuthPrincipal principal, UUID documentId, Map<String, Object> patch) {
        principal.requireManager();
        if (patch.isEmpty() || !PATCHABLE.containsAll(patch.keySet())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
        }
        UUID wid = principal.workspaceId();
        return tenant.run(principal, () -> {
            docs.lockDocument(wid, documentId).orElseThrow(DocumentService::notFound);
            MetaSources now = docs.metaSources(wid, documentId);
            String title = now.title();
            String titleSource = now.titleSource();
            String description = now.description();
            String descriptionSource = now.descriptionSource();
            UUID categoryId = now.categoryId();
            String categorySource = now.categorySource();
            String language = now.language();
            String languageSource = now.languageSource();
            String tagsSource = now.tagsSource();

            List<String> changed = new ArrayList<>();
            if (patch.containsKey("title")) {
                title = text(patch.get("title"), 200, false, "title");
                titleSource = "USER";
                changed.add("title");
            }
            if (patch.containsKey("description")) {
                description = text(patch.get("description"), 2000, true, "description");
                descriptionSource = "USER";
                changed.add("description");
            }
            if (patch.containsKey("language")) {
                language = text(patch.get("language"), 10, true, "language");
                languageSource = "USER";
                changed.add("language");
            }
            if (patch.containsKey("categoryId")) {
                Object rawCat = patch.get("categoryId");
                if (rawCat == null) {
                    categoryId = null;
                } else {
                    UUID parsedCatId;
                    try {
                        parsedCatId = rawCat instanceof UUID u ? u : UUID.fromString(rawCat.toString());
                    } catch (IllegalArgumentException e) {
                        throw invalid("categoryId");
                    }
                    Category cat = categories.find(wid, parsedCatId).orElseThrow(CategoryService::notFound);
                    if (cat.status() == CategoryStatus.ARCHIVED) {
                        throw new ApiException(HttpStatus.BAD_REQUEST, "CATEGORY_ARCHIVED", "Archived categories cannot be assigned.");
                    }
                    categoryId = parsedCatId;
                }
                categorySource = "USER";
                changed.add("categoryId");
            }
            if (patch.containsKey("tags")) {
                Object rawTags = patch.get("tags");
                if (rawTags == null) {
                    tagService.assignTags(wid, documentId, List.of());
                } else if (rawTags instanceof List<?> list) {
                    List<String> tagStrings = new ArrayList<>();
                    for (Object item : list) {
                        if (item == null) throw invalid("tags");
                        tagStrings.add(item.toString());
                    }
                    tagService.assignTags(wid, documentId, tagStrings);
                } else {
                    throw invalid("tags");
                }
                tagsSource = "USER";
                changed.add("tags");
            }

            docs.updateMetadata(wid, documentId, title, titleSource, description, descriptionSource,
                    categoryId, categorySource, language, languageSource, tagsSource);
            audit.record(principal, "DOCUMENT_METADATA_UPDATED", "DOCUMENT", documentId, Map.of("fields", changed));
            return view(wid, documentId, principal);
        });
    }

    /**
     * Changes document visibility and department restriction (UC-11, FR-25).
     * Updates visibility and accessRevision, updates document_departments, updates pending ingest access
     * (Race §7.1), enqueues ACCESS_UPDATED, records audit log, and waits up to 2 seconds for outbox delivery.
     */
    public VisibilityResponse updateVisibility(AuthPrincipal principal, UUID documentId,
                                               String rawVisibility, List<UUID> rawDepartmentIds) {
        principal.requireManager();
        if (rawVisibility == null || (!"WORKSPACE".equals(rawVisibility) && !"DEPARTMENTS".equals(rawVisibility))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Visibility must be WORKSPACE or DEPARTMENTS.");
        }
        UUID wid = principal.workspaceId();

        OutboxEvent event = tenant.run(principal, () -> {
            List<UUID> effectiveDepartmentIds = resolveDepartments(wid, rawVisibility, rawDepartmentIds);

            DocumentHead head = docs.lockDocument(wid, documentId).orElseThrow(DocumentService::notFound);

            long newRev = head.accessRevision() + 1;
            docs.updateVisibility(wid, documentId, rawVisibility, newRev);
            docs.setDocumentDepartments(wid, documentId, effectiveDepartmentIds);

            // Race §7.1: update pending INGEST_REQUESTED outbox events in the same transaction
            outbox.updatePendingIngestAccess(wid, documentId, rawVisibility, effectiveDepartmentIds, newRev);

            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("workspaceId", wid);
            payload.put("visibility", rawVisibility);
            payload.put("departmentIds", effectiveDepartmentIds);
            payload.put("accessRevision", newRev);
            // Leased and not announced: sent below on this thread, retried by the dispatcher only if that fails.
            OutboxEvent enqueued = outbox.enqueueLeased(wid, documentId, OutboxEvent.Type.ACCESS_UPDATED, payload);

            audit.record(principal, "DOCUMENT_VISIBILITY_UPDATED", "DOCUMENT", documentId,
                    Map.of("visibility", rawVisibility, "departmentIds", effectiveDepartmentIds, "accessRevision", newRev));

            return enqueued;
        });

        boolean applied = outboxDispatcher.sendDirect(event, Duration.ofSeconds(2));
        return new VisibilityResponse(applied ? "APPLIED" : "PENDING");
    }

    // ---- reads ----------------------------------------------------------------------------------

    public record DocumentPage(List<DocumentView> items, String nextCursor, boolean hasMore) {
    }

    public DocumentPage list(AuthPrincipal principal, String status, UUID categoryId, String tag,
                             String query, Cursor cursor, int limit) {
        return tenant.run(principal, () -> {
            List<DocumentDetail> rows = new ArrayList<>(docs.listVisible(principal, status, categoryId, tag, query, cursor, limit + 1));
            boolean more = rows.size() > limit;
            if (more) {
                rows.remove(rows.size() - 1);
            }
            String next = more ? new Cursor(rows.get(rows.size() - 1).createdAt(), rows.get(rows.size() - 1).id())
                    .encode() : null;
            return new DocumentPage(rows.stream().map(d -> DocumentView.of(d, principal)).toList(), next, more);
        });
    }

    /** 404 when the document does not exist or is outside the caller's read scope (no name leak). */
    public DocumentView get(AuthPrincipal principal, UUID documentId) {
        return tenant.run(principal, () -> DocumentView.of(
                docs.findVisible(principal, documentId).orElseThrow(DocumentService::notFound), principal));
    }

    public record DownloadUrl(String url, Instant expiresAt) {
    }

    public DownloadUrl downloadUrl(AuthPrincipal principal, UUID documentId) {
        VersionRow version = tenant.run(principal, () -> {
            DocumentDetail d = docs.findVisible(principal, documentId).orElseThrow(DocumentService::notFound);
            return d.current() != null ? d.current() : d.latest();
        });
        Instant expires = Instant.now().plus(DOWNLOAD_TTL);
        return new DownloadUrl(presign(version), expires);
    }

    public List<DocumentView.VersionHistory> versions(AuthPrincipal principal, UUID documentId) {
        principal.requireManager();
        return tenant.run(principal, () -> {
            docs.findDetail(principal.workspaceId(), documentId).orElseThrow(DocumentService::notFound);
            return docs.versionsOf(principal.workspaceId(), documentId).stream()
                    .map(DocumentView.VersionHistory::of).toList();
        });
    }

    // ---- helpers --------------------------------------------------------------------------------

    /**
     * The distinct (order kept) department ids of a DEPARTMENTS document, each checked against the caller's
     * workspace and not archived; empty for WORKSPACE visibility.
     */
    private List<UUID> resolveDepartments(UUID wid, String visibility, List<UUID> requested) {
        if (!"DEPARTMENTS".equals(visibility)) {
            return List.of();
        }
        if (requested == null || requested.isEmpty()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED",
                    "At least one department is required for DEPARTMENTS visibility.");
        }
        List<UUID> distinct = new ArrayList<>(new LinkedHashSet<>(requested));
        for (UUID deptId : distinct) {
            Department d = deptId == null ? null : departments.find(wid, deptId).orElse(null);
            if (d == null) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED",
                        "A selected department does not exist in this workspace.");
            }
            if (d.status() == DepartmentStatus.ARCHIVED) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED",
                        "Archived departments cannot be assigned.");
            }
        }
        return distinct;
    }

    private DocumentView view(UUID wid, UUID documentId, AuthPrincipal viewer) {
        return DocumentView.of(docs.findDetail(wid, documentId).orElseThrow(), viewer);
    }

    private void checkQuota(UUID wid, boolean newDocument, long incomingBytes) {
        if (quota.docsPerWorkspace() <= 0 && quota.bytesPerWorkspace() <= 0) {
            return;
        }
        Usage used = docs.usage(wid);
        if (newDocument && quota.docsPerWorkspace() > 0 && used.documents() >= quota.docsPerWorkspace()) {
            throw quotaExceeded("documents", quota.docsPerWorkspace(), used.documents());
        }
        if (quota.bytesPerWorkspace() > 0 && used.bytes() + incomingBytes > quota.bytesPerWorkspace()) {
            throw quotaExceeded("bytes", quota.bytesPerWorkspace(), used.bytes());
        }
    }

    private static ApiException quotaExceeded(String kind, long limit, long used) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("kind", kind);
        details.put("limit", limit);
        details.put("used", used);
        return new ApiException(HttpStatus.CONFLICT, "QUOTA_EXCEEDED",
                "The workspace has reached its document limit.", details);
    }

    private static ApiException duplicate(Duplicate d) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("documentId", d.documentId());
        details.put("title", d.title());
        details.put("createdAt", d.createdAt());
        return new ApiException(HttpStatus.CONFLICT, "DUPLICATE_DOCUMENT",
                "This file is already in the workspace as \"" + d.title() + "\".", details);
    }

    private void putObject(String key, byte[] content, String mimeType) {
        try {
            storage.put(key, content, mimeType);
        } catch (RuntimeException e) {
            log.error("Object storage write failed: {}", e.getClass().getSimpleName());
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "File storage is unavailable. Try again later.");
        }
    }

    private String presign(VersionRow version) {
        try {
            return storage.presignGet(version.objectKey(), version.originalName(), DOWNLOAD_TTL);
        } catch (RuntimeException e) {
            log.error("Pre-signing failed: {}", e.getClass().getSimpleName());
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "File storage is unavailable. Try again later.");
        }
    }

    static Map<String, Object> ingestPayload(UUID wid, UUID documentId, UUID versionId, int versionNo,
                                             String objectKey, Validated file, int attempt, String title,
                                             String visibility, List<UUID> departmentIds, long accessRevision) {
        Map<String, Object> access = new LinkedHashMap<>();
        access.put("visibility", visibility);
        access.put("departmentIds", departmentIds);
        access.put("accessRevision", accessRevision);
        Map<String, Object> suggest = new LinkedHashMap<>();
        suggest.put("enabled", false);
        suggest.put("categories", List.of());
        suggest.put("tags", List.of());
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("workspaceId", wid);
        payload.put("documentId", documentId);
        payload.put("versionId", versionId);
        payload.put("versionNo", versionNo);
        payload.put("objectKey", objectKey);
        payload.put("sha256", file.sha256Hex());
        payload.put("attempt", attempt);
        payload.put("fileType", file.type().name());
        payload.put("mimeType", file.type().mimeType());
        payload.put("originalName", file.originalName());
        payload.put("title", title);
        payload.put("access", access);
        payload.put("suggest", suggest);
        return payload;
    }

    static String objectKey(UUID wid, UUID documentId, UUID versionId) {
        return "workspaces/" + wid + "/documents/" + documentId + "/versions/" + versionId;
    }

    static String titleFrom(String originalName) {
        int dot = originalName.lastIndexOf('.');
        String base = (dot > 0 ? originalName.substring(0, dot) : originalName).strip();
        if (base.isEmpty()) {
            base = originalName.strip();
        }
        return base.length() <= 200 ? base : base.substring(0, 200).strip();
    }

    private static String text(Object raw, int max, boolean nullable, String field) {
        if (raw == null) {
            if (nullable) {
                return null;
            }
            throw invalid(field);
        }
        if (!(raw instanceof String s)) {
            throw invalid(field);
        }
        String value = s.strip();
        if (value.isEmpty()) {
            if (nullable) {
                return null;
            }
            throw invalid(field);
        }
        if (value.length() > max) {
            throw invalid(field);
        }
        return value;
    }

    private static ApiException invalid(String field) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.",
                Map.of("fields", Map.of(field, "invalid")));
    }

    static ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Document not found.");
    }
}
