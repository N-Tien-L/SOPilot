package com.sopilot.core.category;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * {@code core.categories}. Read and write queries always filter by {@code workspace_id}
 * alongside RLS (TECH-V2-core-api §3.4, §5.6).
 */
@Repository
public class CategoryRepository {

    public enum CategoryStatus { ACTIVE, ARCHIVED }

    public record Category(UUID id, UUID workspaceId, String name, CategoryStatus status,
                            OffsetDateTime createdAt, OffsetDateTime updatedAt) {
    }

    private static final RowMapper<Category> ROW_MAPPER = (rs, i) -> new Category(
            rs.getObject("id", UUID.class),
            rs.getObject("workspace_id", UUID.class),
            rs.getString("name"),
            CategoryStatus.valueOf(rs.getString("status")),
            rs.getObject("created_at", OffsetDateTime.class),
            rs.getObject("updated_at", OffsetDateTime.class));

    private final JdbcTemplate jdbc;

    public CategoryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Category> find(UUID workspaceId, UUID id) {
        return jdbc.query("SELECT id, workspace_id, name, status, created_at, updated_at FROM core.categories "
                        + "WHERE workspace_id = ? AND id = ?",
                ROW_MAPPER, workspaceId, id).stream().findFirst();
    }

    public Optional<Category> findByName(UUID workspaceId, String name) {
        return jdbc.query("SELECT id, workspace_id, name, status, created_at, updated_at FROM core.categories "
                        + "WHERE workspace_id = ? AND lower(name) = lower(?)",
                ROW_MAPPER, workspaceId, name).stream().findFirst();
    }

    public List<Category> list(UUID workspaceId, boolean includeArchived) {
        String sql = "SELECT id, workspace_id, name, status, created_at, updated_at FROM core.categories "
                + "WHERE workspace_id = ?"
                + (includeArchived ? "" : " AND status = 'ACTIVE'")
                + " ORDER BY lower(name) ASC, id ASC";
        return jdbc.query(sql, ROW_MAPPER, workspaceId);
    }

    public void insert(UUID id, UUID workspaceId, String name) {
        jdbc.update("INSERT INTO core.categories (id, workspace_id, name, status) VALUES (?, ?, ?, 'ACTIVE')",
                id, workspaceId, name);
    }

    public void update(UUID workspaceId, UUID id, String name, CategoryStatus status) {
        jdbc.update("UPDATE core.categories SET name = ?, status = ? WHERE workspace_id = ? AND id = ?",
                name, status.name(), workspaceId, id);
    }

    public void delete(UUID workspaceId, UUID id) {
        jdbc.update("DELETE FROM core.categories WHERE workspace_id = ? AND id = ?", workspaceId, id);
    }
}
