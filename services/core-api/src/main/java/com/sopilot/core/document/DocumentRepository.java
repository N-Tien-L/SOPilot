package com.sopilot.core.document;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.common.Cursor;
import com.sopilot.core.security.AuthPrincipal;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * {@code core.documents} and {@code core.document_versions}. Every call needs the RLS context of the
 * workspace (TECH §4.2); the explicit {@code workspace_id} predicates repeat what RLS enforces so the
 * queries stay correct and index-friendly. Soft-deleted documents are invisible to every read here.
 */
@Repository
public class DocumentRepository {

    private static final String VERSION_COLUMNS = "%1$s.id AS %2$sid, %1$s.document_id AS %2$sdocument_id, "
            + "%1$s.version_no AS %2$sversion_no, %1$s.status AS %2$sstatus, %1$s.failure_code AS %2$sfailure_code, "
            + "%1$s.failure_message AS %2$sfailure_message, %1$s.original_name AS %2$soriginal_name, "
            + "%1$s.mime_type AS %2$smime_type, %1$s.file_type AS %2$sfile_type, %1$s.size_bytes AS %2$ssize_bytes, "
            + "%1$s.sha256 AS %2$ssha256, %1$s.object_key AS %2$sobject_key, %1$s.page_count AS %2$spage_count, "
            + "%1$s.detected_language AS %2$sdetected_language, %1$s.doc_code AS %2$sdoc_code, "
            + "%1$s.revision_label AS %2$srevision_label, %1$s.effective_date AS %2$seffective_date, "
            + "%1$s.warning_codes AS %2$swarning_codes, %1$s.attempt AS %2$sattempt, %1$s.created_at AS %2$screated_at, "
            + "%1$s.uploaded_by AS %2$suploaded_by";

    private static final String DETAIL_SELECT = "SELECT d.id, d.title, d.description, d.language, d.visibility, "
            + "d.access_revision, d.current_version_id, d.latest_version_id, d.created_by, u.display_name AS creator_name, "
            + "d.created_at, d.updated_at, d.category_id, c.name AS category_name, "
            + "d.title_source, d.description_source, d.category_source, d.tags_source, d.language_source, "
            + "d.owner_department_id, ds.title AS suggested_title, ds.proposed_category_name AS suggested_category, "
            + "COALESCE((SELECT array_agg(t.name ORDER BY lower(t.name) ASC) FROM core.document_tags dt "
            + " JOIN core.tags t ON t.workspace_id = dt.workspace_id AND t.id = dt.tag_id "
            + " WHERE dt.workspace_id = d.workspace_id AND dt.document_id = d.id), ARRAY[]::text[]) AS doc_tags, "
            + "COALESCE((SELECT jsonb_agg(jsonb_build_object('id', dep.id, 'name', dep.name) ORDER BY lower(dep.name) ASC) "
            + " FROM core.document_departments dd JOIN core.departments dep ON dep.workspace_id = dd.workspace_id AND dep.id = dd.department_id "
            + " WHERE dd.workspace_id = d.workspace_id AND dd.document_id = d.id), '[]'::jsonb)::text AS doc_departments, "
            + VERSION_COLUMNS.formatted("lv", "lv_") + ", " + VERSION_COLUMNS.formatted("cv", "cv_")
            + " FROM core.documents d "
            + "LEFT JOIN core.categories c ON c.workspace_id = d.workspace_id AND c.id = d.category_id "
            + "JOIN core.document_versions lv ON lv.id = d.latest_version_id "
            + "LEFT JOIN core.document_versions cv ON cv.id = d.current_version_id "
            + "LEFT JOIN core.document_suggestions ds ON ds.workspace_id = d.workspace_id "
            + " AND ds.version_id = d.current_version_id "
            + "LEFT JOIN core.users u ON u.id = d.created_by";

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final RowMapper<DocumentDetail> detailMapper;

    public DocumentRepository(JdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
        this.detailMapper = (rs, i) -> {
            UUID categoryId = rs.getObject("category_id", UUID.class);
            CategoryRef category = categoryId == null ? null : new CategoryRef(categoryId, rs.getString("category_name"));
            java.sql.Array tagsArr = rs.getArray("doc_tags");
            List<String> tags = tagsArr == null ? List.of() : List.of((String[]) tagsArr.getArray());
            List<DepartmentRef> departments = parseDepartments(rs.getString("doc_departments"));
            FieldSources fieldSources = new FieldSources(
                    rs.getString("title_source"), rs.getString("description_source"),
                    rs.getString("category_source"), rs.getString("tags_source"),
                    rs.getString("language_source"));
            // Only what the document does not already show: the title unless the user set it or it is the same,
            // and a proposed category name only while the document has no category.
            String title = rs.getString("title");
            String suggestedTitle = rs.getString("suggested_title");
            if ("USER".equals(fieldSources.title()) || suggestedTitle == null || suggestedTitle.equals(title)) {
                suggestedTitle = null;
            }
            String suggestedCategory = categoryId == null ? rs.getString("suggested_category") : null;
            Suggestions suggestions = suggestedTitle == null && suggestedCategory == null
                    ? null : new Suggestions(suggestedTitle, suggestedCategory);
            return new DocumentDetail(
                    rs.getObject("id", UUID.class), title, rs.getString("description"),
                    rs.getString("language"), rs.getString("visibility"), rs.getLong("access_revision"),
                    rs.getObject("created_by", UUID.class), rs.getString("creator_name"),
                    rs.getObject("created_at", OffsetDateTime.class), rs.getObject("updated_at", OffsetDateTime.class),
                    version(rs, "lv_"), version(rs, "cv_"), category, tags, departments, fieldSources,
                    rs.getObject("owner_department_id", UUID.class), suggestions);
        };
    }

    private List<DepartmentRef> parseDepartments(String jsonStr) {
        if (jsonStr == null || jsonStr.isBlank() || "[]".equals(jsonStr)) {
            return List.of();
        }
        try {
            return mapper.readValue(jsonStr, new TypeReference<List<DepartmentRef>>() {});
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Document departments could not be read");
        }
    }

    // ---- reads ----------------------------------------------------------------------------------

    /** Locks the document row, serializing concurrent version changes of the same document. */
    public Optional<DocumentHead> lockDocument(UUID workspaceId, UUID documentId) {
        return jdbc.query("SELECT id, title, visibility, access_revision, current_version_id, latest_version_id, "
                        + "owner_department_id "
                        + "FROM core.documents WHERE workspace_id = ? AND id = ? AND deleted_at IS NULL FOR UPDATE",
                (rs, i) -> new DocumentHead(rs.getObject("id", UUID.class), rs.getString("title"),
                        rs.getString("visibility"), rs.getLong("access_revision"),
                        rs.getObject("current_version_id", UUID.class), rs.getObject("latest_version_id", UUID.class),
                        rs.getObject("owner_department_id", UUID.class)),
                workspaceId, documentId).stream().findFirst();
    }

    public Optional<DocumentDetail> findDetail(UUID workspaceId, UUID documentId) {
        return jdbc.query(DETAIL_SELECT + " WHERE d.workspace_id = ? AND d.id = ? AND d.deleted_at IS NULL",
                detailMapper, workspaceId, documentId).stream().findFirst();
    }

    /** Applies the read filter of TECH §5.6: managers see everything, others WORKSPACE or their department. */
    public Optional<DocumentDetail> findVisible(AuthPrincipal principal, UUID documentId) {
        return jdbc.query(DETAIL_SELECT + " WHERE d.workspace_id = ? AND d.id = ? AND d.deleted_at IS NULL AND "
                        + VISIBLE, detailMapper, principal.workspaceId(), documentId,
                principal.isManager(), principal.departmentId(), principal.departmentId()).stream().findFirst();
    }

    /**
     * The read filter of {@link #findVisible} without loading anything: write endpoints answer {@code 404} for a
     * document the caller cannot read before they say {@code 403} (ADR-007, no name leak).
     */
    public boolean isVisibleTo(AuthPrincipal principal, UUID documentId) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM core.documents d "
                        + "WHERE d.workspace_id = ? AND d.id = ? AND d.deleted_at IS NULL AND " + VISIBLE + ")",
                Boolean.class, principal.workspaceId(), documentId,
                principal.isManager(), principal.departmentId(), principal.departmentId()));
    }

    public List<DocumentDetail> listVisible(AuthPrincipal principal, String status, UUID categoryId, String tag,
                                            String titleQuery, Cursor cursor, int limitPlusOne) {
        StringBuilder sql = new StringBuilder(DETAIL_SELECT
                + " WHERE d.workspace_id = ? AND d.deleted_at IS NULL AND " + VISIBLE);
        List<Object> args = new ArrayList<>(List.of(principal.workspaceId()));
        args.add(principal.isManager());
        args.add(principal.departmentId());
        args.add(principal.departmentId());
        if (status != null) {
            sql.append(" AND lv.status = ?");
            args.add(status);
        }
        if (categoryId != null) {
            sql.append(" AND d.category_id = ?");
            args.add(categoryId);
        }
        if (tag != null && !tag.isBlank()) {
            sql.append(" AND EXISTS (SELECT 1 FROM core.document_tags dt "
                    + "JOIN core.tags t ON t.workspace_id = dt.workspace_id AND t.id = dt.tag_id "
                    + "WHERE dt.workspace_id = d.workspace_id AND dt.document_id = d.id AND lower(t.name) = lower(?))");
            args.add(tag.trim());
        }
        if (titleQuery != null && !titleQuery.isBlank()) {
            sql.append(" AND d.title ILIKE ? ESCAPE '\\'");
            args.add("%" + titleQuery.trim().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%");
        }
        if (cursor != null) {
            sql.append(" AND (d.created_at, d.id) < (?, ?)");
            args.add(cursor.createdAt());
            args.add(cursor.id());
        }
        sql.append(" ORDER BY d.created_at DESC, d.id DESC LIMIT ?");
        args.add(limitPlusOne);
        return jdbc.query(sql.toString(), detailMapper, args.toArray());
    }

    public Optional<VersionRow> findVersion(UUID workspaceId, UUID documentId, UUID versionId) {
        return jdbc.query("SELECT " + VERSION_COLUMNS.formatted("v", "v_") + " FROM core.document_versions v "
                        + "WHERE v.workspace_id = ? AND v.document_id = ? AND v.id = ?",
                (rs, i) -> version(rs, "v_"), workspaceId, documentId, versionId).stream().findFirst();
    }

    public Optional<VersionRow> findVersionForUpdate(UUID workspaceId, UUID documentId, UUID versionId) {
        return jdbc.query("SELECT " + VERSION_COLUMNS.formatted("v", "v_") + " FROM core.document_versions v "
                        + "WHERE v.workspace_id = ? AND v.document_id = ? AND v.id = ? FOR UPDATE",
                (rs, i) -> version(rs, "v_"), workspaceId, documentId, versionId).stream().findFirst();
    }

    /** Versions newest first, each with the display name of whoever uploaded it. */
    public List<VersionWithUploader> versionsOf(UUID workspaceId, UUID documentId) {
        return jdbc.query("SELECT " + VERSION_COLUMNS.formatted("v", "v_") + ", u.display_name AS uploader_name "
                        + "FROM core.document_versions v LEFT JOIN core.users u ON u.id = v.uploaded_by "
                        + "WHERE v.workspace_id = ? AND v.document_id = ? ORDER BY v.version_no DESC",
                (rs, i) -> new VersionWithUploader(version(rs, "v_"), rs.getString("uploader_name")),
                workspaceId, documentId);
    }

    public int maxVersionNo(UUID workspaceId, UUID documentId) {
        Integer max = jdbc.queryForObject("SELECT coalesce(max(version_no), 0) FROM core.document_versions "
                + "WHERE workspace_id = ? AND document_id = ?", Integer.class, workspaceId, documentId);
        return max == null ? 0 : max;
    }

    /**
     * A current (non-{@code SUPERSEDED}) version with these bytes in another live document of the workspace
     * (TECH §3.3). {@code exceptDocumentId} is null when creating a new document.
     */
    public Optional<Duplicate> findDuplicate(UUID workspaceId, byte[] sha256, UUID exceptDocumentId) {
        return jdbc.query("SELECT d.id, d.title, d.created_at FROM core.document_versions v "
                        + "JOIN core.documents d ON d.workspace_id = v.workspace_id AND d.id = v.document_id "
                        + "WHERE v.workspace_id = ? AND v.sha256 = ? AND v.status <> 'SUPERSEDED' "
                        + "AND d.deleted_at IS NULL AND (?::uuid IS NULL OR d.id <> ?::uuid) "
                        + "ORDER BY d.created_at LIMIT 1",
                (rs, i) -> new Duplicate(rs.getObject("id", UUID.class), rs.getString("title"),
                        rs.getObject("created_at", OffsetDateTime.class)),
                workspaceId, sha256, exceptDocumentId, exceptDocumentId).stream().findFirst();
    }

    public Usage usage(UUID workspaceId) {
        return jdbc.queryForObject("SELECT (SELECT count(*) FROM core.documents WHERE workspace_id = ? "
                        + "AND deleted_at IS NULL), "
                        + "(SELECT coalesce(sum(v.size_bytes), 0) FROM core.document_versions v "
                        + " JOIN core.documents d ON d.workspace_id = v.workspace_id AND d.id = v.document_id "
                        + " WHERE v.workspace_id = ? AND v.status <> 'SUPERSEDED' AND d.deleted_at IS NULL)",
                (rs, i) -> new Usage(rs.getLong(1), rs.getLong(2)), workspaceId, workspaceId);
    }

    public List<UUID> departmentIds(UUID workspaceId, UUID documentId) {
        return jdbc.queryForList("SELECT department_id FROM core.document_departments "
                + "WHERE workspace_id = ? AND document_id = ? ORDER BY department_id", UUID.class, workspaceId, documentId);
    }

    public List<String> objectKeys(UUID workspaceId, UUID documentId) {
        return jdbc.queryForList("SELECT object_key FROM core.document_versions WHERE workspace_id = ? "
                + "AND document_id = ?", String.class, workspaceId, documentId);
    }

    // ---- writes ---------------------------------------------------------------------------------

    /**
     * {@code ownerDepartmentId} is null exactly for {@code WORKSPACE}. The foreign key tying it to
     * {@code document_departments} is checked at commit, so insert the departments in the same transaction.
     */
    public void insertDocument(UUID id, UUID workspaceId, String title, String titleSource, UUID versionId,
                               UUID createdBy, String visibility, UUID ownerDepartmentId, UUID categoryId,
                               String categorySource, String tagsSource) {
        jdbc.update("INSERT INTO core.documents (id, workspace_id, title, title_source, latest_version_id, "
                        + "created_by, visibility, owner_department_id, category_id, category_source, tags_source) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                id, workspaceId, title, titleSource, versionId, createdBy, visibility, ownerDepartmentId, categoryId,
                categorySource, tagsSource);
    }

    public void insertVersion(UUID id, UUID workspaceId, UUID documentId, int versionNo, String originalName,
                              String mimeType, String fileType, long size, byte[] sha256, String objectKey,
                              UUID uploadedBy) {
        jdbc.update("INSERT INTO core.document_versions (id, workspace_id, document_id, version_no, status, "
                        + "original_name, mime_type, file_type, size_bytes, sha256, object_key, uploaded_by) "
                        + "VALUES (?, ?, ?, ?, 'UPLOADED', ?, ?, ?, ?, ?, ?, ?)",
                id, workspaceId, documentId, versionNo, originalName, mimeType, fileType, size, sha256, objectKey,
                uploadedBy);
    }

    public void setLatestVersion(UUID workspaceId, UUID documentId, UUID versionId) {
        jdbc.update("UPDATE core.documents SET latest_version_id = ? WHERE workspace_id = ? AND id = ?",
                versionId, workspaceId, documentId);
    }

    /** UPLOADED again with a higher attempt, failure cleared (the retry path). */
    public void resetForRetry(UUID workspaceId, UUID versionId, int attempt) {
        jdbc.update("UPDATE core.document_versions SET status = 'UPLOADED', attempt = ?, failure_code = NULL, "
                + "failure_message = NULL, processed_at = NULL WHERE workspace_id = ? AND id = ?",
                attempt, workspaceId, versionId);
    }

    public void setStatus(UUID workspaceId, UUID versionId, String status) {
        jdbc.update("UPDATE core.document_versions SET status = ?, failure_code = NULL, failure_message = NULL "
                + "WHERE workspace_id = ? AND id = ?", status, workspaceId, versionId);
    }

    public void markFailed(UUID workspaceId, UUID versionId, String code, String message) {
        jdbc.update("UPDATE core.document_versions SET status = 'FAILED', failure_code = ?, failure_message = ?, "
                + "processed_at = now() WHERE workspace_id = ? AND id = ?", code, message, workspaceId, versionId);
    }

    public void markReady(UUID workspaceId, UUID versionId, Integer pageCount, String detectedLanguage,
                          Integer chunkCount, String embeddingModel, String embeddingRevision, String docCode,
                          String revisionLabel, LocalDate effectiveDate, String[] warningCodes) {
        jdbc.update("UPDATE core.document_versions SET status = 'READY', failure_code = NULL, failure_message = NULL, "
                        + "page_count = ?, detected_language = ?, chunk_count = ?, embedding_model = ?, "
                        + "embedding_revision = ?, doc_code = ?, revision_label = ?, effective_date = ?, "
                        + "warning_codes = ?, processed_at = now() WHERE workspace_id = ? AND id = ?",
                pageCount, detectedLanguage, chunkCount, embeddingModel, embeddingRevision, docCode, revisionLabel,
                effectiveDate, warningCodes, workspaceId, versionId);
    }

    /** Makes {@code versionId} the Q&A version and supersedes every older version, FAILED ones included. */
    public List<String> activate(UUID workspaceId, UUID documentId, UUID versionId, int versionNo, String detectedLanguage) {
        List<String> superseded = jdbc.queryForList("UPDATE core.document_versions SET status = 'SUPERSEDED' "
                + "WHERE workspace_id = ? AND document_id = ? AND version_no < ? AND status <> 'SUPERSEDED' RETURNING object_key",
                String.class, workspaceId, documentId, versionNo);
        jdbc.update("UPDATE core.documents SET current_version_id = ?, "
                        + "language = CASE WHEN language_source = 'SYSTEM' AND ?::text IS NOT NULL THEN ? ELSE language END "
                        + "WHERE workspace_id = ? AND id = ?", versionId, detectedLanguage, detectedLanguage, workspaceId, documentId);
        return superseded;
    }

    public void updateMetadata(UUID workspaceId, UUID documentId, String title, String titleSource, String description,
                               String descriptionSource, UUID categoryId, String categorySource, String language,
                               String languageSource, String tagsSource) {
        jdbc.update("UPDATE core.documents SET title = ?, title_source = ?, description = ?, description_source = ?, "
                        + "category_id = ?, category_source = ?, language = ?, language_source = ?, tags_source = ? "
                        + "WHERE workspace_id = ? AND id = ?",
            title, titleSource, description, descriptionSource, categoryId, categorySource, language,
            languageSource, tagsSource, workspaceId, documentId);
    }

    /** Keeps the latest suggestion per version (V2-25); the document fields are changed separately. */
    public void upsertSuggestion(UUID workspaceId, UUID documentId, UUID versionId, String method, String title,
                                 String description, UUID categoryId, String proposedCategoryName, String[] tags) {
        jdbc.update("INSERT INTO core.document_suggestions (workspace_id, version_id, document_id, method, title, "
                        + "description, category_id, proposed_category_name, tags) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                        + "ON CONFLICT (version_id) DO UPDATE SET method = EXCLUDED.method, title = EXCLUDED.title, "
                        + "description = EXCLUDED.description, category_id = EXCLUDED.category_id, "
                        + "proposed_category_name = EXCLUDED.proposed_category_name, tags = EXCLUDED.tags, "
                        + "updated_at = now()",
                workspaceId, versionId, documentId, method, title, description, categoryId, proposedCategoryName, tags);
    }

    public void updateVisibility(UUID workspaceId, UUID documentId, String visibility, long accessRevision) {
        jdbc.update("UPDATE core.documents SET visibility = ?, access_revision = ? WHERE workspace_id = ? AND id = ?",
                visibility, accessRevision, workspaceId, documentId);
    }

    /** Visibility, owner department and revision in one statement: the CHECK ties the first two together. */
    public void updateOwnership(UUID workspaceId, UUID documentId, String visibility, UUID ownerDepartmentId,
                                long accessRevision) {
        jdbc.update("UPDATE core.documents SET visibility = ?, owner_department_id = ?, access_revision = ? "
                        + "WHERE workspace_id = ? AND id = ?",
                visibility, ownerDepartmentId, accessRevision, workspaceId, documentId);
    }

    public void setDocumentDepartments(UUID workspaceId, UUID documentId, List<UUID> departmentIds) {
        jdbc.update("DELETE FROM core.document_departments WHERE workspace_id = ? AND document_id = ?",
                workspaceId, documentId);
        if (departmentIds != null) {
            for (UUID deptId : departmentIds) {
                jdbc.update("INSERT INTO core.document_departments (workspace_id, document_id, department_id) VALUES (?, ?, ?)",
                        workspaceId, documentId, deptId);
            }
        }
    }

    public MetaSources metaSources(UUID workspaceId, UUID documentId) {
        return jdbc.queryForObject("SELECT title, title_source, description, description_source, category_id, "
                        + "category_source, language, language_source, tags_source FROM core.documents "
                        + "WHERE workspace_id = ? AND id = ?",
                (rs, i) -> new MetaSources(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getObject(5, UUID.class), rs.getString(6), rs.getString(7), rs.getString(8), rs.getString(9)),
                workspaceId, documentId);
    }

    public List<UUID> liveDocumentIds(UUID workspaceId) {
        return jdbc.queryForList("SELECT id FROM core.documents WHERE workspace_id = ? AND deleted_at IS NULL "
                + "ORDER BY id", UUID.class, workspaceId);
    }

    public void softDelete(UUID workspaceId, UUID documentId) {
        jdbc.update("UPDATE core.documents SET deleted_at = now() WHERE workspace_id = ? AND id = ?", workspaceId, documentId);
    }

    /** Hard delete once ai-service confirmed its side is gone; versions cascade. */
    public void hardDelete(UUID workspaceId, UUID documentId) {
        jdbc.update("DELETE FROM core.documents WHERE workspace_id = ? AND id = ?", workspaceId, documentId);
    }

    // ---- locks ----------------------------------------------------------------------------------

    /** Transaction-scoped advisory lock; blocks until free, released at commit or rollback. */
    public void advisoryLock(String name) {
        jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", rs -> { }, name);
    }

    // ---- mapping --------------------------------------------------------------------------------

    private static final String VISIBLE = "(?::boolean OR d.visibility = 'WORKSPACE' OR (?::uuid IS NOT NULL AND "
            + "EXISTS (SELECT 1 FROM core.document_departments dd WHERE dd.document_id = d.id "
            + "AND dd.department_id = ?::uuid)))";

    private static VersionRow version(ResultSet rs, String p) throws SQLException {
        if (rs.getObject(p + "id") == null) {
            return null;
        }
        java.sql.Array warnings = rs.getArray(p + "warning_codes");
        java.sql.Date effective = rs.getDate(p + "effective_date");
        return new VersionRow(rs.getObject(p + "id", UUID.class), rs.getObject(p + "document_id", UUID.class),
                rs.getInt(p + "version_no"), rs.getString(p + "status"), rs.getString(p + "failure_code"),
                rs.getString(p + "failure_message"), rs.getString(p + "original_name"), rs.getString(p + "mime_type"),
                rs.getString(p + "file_type"), rs.getLong(p + "size_bytes"), rs.getBytes(p + "sha256"),
                rs.getString(p + "object_key"), (Integer) rs.getObject(p + "page_count"),
                rs.getString(p + "detected_language"), rs.getString(p + "doc_code"),
                rs.getString(p + "revision_label"), effective == null ? null : effective.toLocalDate(),
                warnings == null ? new String[0] : (String[]) warnings.getArray(), rs.getInt(p + "attempt"),
                rs.getObject(p + "created_at", OffsetDateTime.class), rs.getObject(p + "uploaded_by", UUID.class));
    }

    public record CategoryRef(UUID id, String name) {
    }

    public record DepartmentRef(UUID id, String name) {
    }

    public record FieldSources(String title, String description, String category, String tags, String language) {
    }

    public record DocumentHead(UUID id, String title, String visibility, long accessRevision, UUID currentVersionId,
                               UUID latestVersionId, UUID ownerDepartmentId) {
    }

    /**
     * Suggested values that are stored but never applied (V2-25): the title (decision of 2026-11-12) and a category
     * name the workspace does not have yet. Either may be {@code null}.
     */
    public record Suggestions(String title, String proposedCategoryName) {
    }

    public record DocumentDetail(UUID id, String title, String description, String language, String visibility,
                                 long accessRevision, UUID createdBy, String creatorName, OffsetDateTime createdAt,
                                 OffsetDateTime updatedAt, VersionRow latest, VersionRow current,
                                 CategoryRef category, List<String> tags, List<DepartmentRef> departments,
                                 FieldSources fieldSources, UUID ownerDepartmentId, Suggestions suggestions) {
        public DocumentDetail(UUID id, String title, String description, String language, String visibility,
                              long accessRevision, UUID createdBy, String creatorName, OffsetDateTime createdAt,
                              OffsetDateTime updatedAt, VersionRow latest, VersionRow current,
                              CategoryRef category, List<String> tags, List<DepartmentRef> departments,
                              FieldSources fieldSources, UUID ownerDepartmentId) {
            this(id, title, description, language, visibility, accessRevision, createdBy, creatorName, createdAt,
                    updatedAt, latest, current, category, tags, departments, fieldSources, ownerDepartmentId, null);
        }
    }

    public record VersionRow(UUID id, UUID documentId, int versionNo, String status, String failureCode,
                             String failureMessage, String originalName, String mimeType, String fileType,
                             long sizeBytes, byte[] sha256, String objectKey, Integer pageCount,
                             String detectedLanguage, String docCode, String revisionLabel, LocalDate effectiveDate,
                             String[] warningCodes, int attempt, OffsetDateTime createdAt, UUID uploadedBy) {
    }

    public record VersionWithUploader(VersionRow version, String uploaderName) {
    }

    public record Duplicate(UUID documentId, String title, OffsetDateTime createdAt) {
    }

    public record Usage(long documents, long bytes) {
    }

    public record MetaSources(String title, String titleSource, String description, String descriptionSource,
                              UUID categoryId, String categorySource, String language, String languageSource,
                              String tagsSource) {
    }
}
