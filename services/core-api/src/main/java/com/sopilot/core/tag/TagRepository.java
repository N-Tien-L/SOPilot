package com.sopilot.core.tag;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * {@code core.tags} and {@code core.document_tags}. Every query filters by {@code workspace_id}
 * alongside RLS (TECH-V2-core-api §3.4, §5.6).
 */
@Repository
public class TagRepository {

    public record Tag(UUID id, UUID workspaceId, String name, OffsetDateTime createdAt) {
    }

    private static final RowMapper<Tag> ROW_MAPPER = (rs, i) -> new Tag(
            rs.getObject("id", UUID.class),
            rs.getObject("workspace_id", UUID.class),
            rs.getString("name"),
            rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcTemplate jdbc;

    public TagRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Tag> list(UUID workspaceId) {
        return jdbc.query("SELECT id, workspace_id, name, created_at FROM core.tags "
                        + "WHERE workspace_id = ? ORDER BY lower(name) ASC, id ASC",
                ROW_MAPPER, workspaceId);
    }

    public Optional<Tag> findByName(UUID workspaceId, String name) {
        return jdbc.query("SELECT id, workspace_id, name, created_at FROM core.tags "
                        + "WHERE workspace_id = ? AND lower(name) = lower(?)",
                ROW_MAPPER, workspaceId, name).stream().findFirst();
    }

    public Tag findOrCreate(UUID id, UUID workspaceId, String name) {
        jdbc.update("INSERT INTO core.tags (id, workspace_id, name) VALUES (?, ?, ?) "
                + "ON CONFLICT (workspace_id, lower(name)) DO NOTHING", id, workspaceId, name);
        return findByName(workspaceId, name).orElseThrow();
    }

    public List<String> findTagsForDocument(UUID workspaceId, UUID documentId) {
        return jdbc.queryForList("SELECT t.name FROM core.tags t "
                        + "JOIN core.document_tags dt ON dt.workspace_id = t.workspace_id AND dt.tag_id = t.id "
                        + "WHERE dt.workspace_id = ? AND dt.document_id = ? ORDER BY lower(t.name) ASC",
                String.class, workspaceId, documentId);
    }

    public void setDocumentTags(UUID workspaceId, UUID documentId, List<UUID> tagIds) {
        jdbc.update("DELETE FROM core.document_tags WHERE workspace_id = ? AND document_id = ?",
                workspaceId, documentId);
        for (UUID tagId : tagIds) {
            jdbc.update("INSERT INTO core.document_tags (workspace_id, document_id, tag_id) VALUES (?, ?, ?)",
                    workspaceId, documentId, tagId);
        }
    }
}
