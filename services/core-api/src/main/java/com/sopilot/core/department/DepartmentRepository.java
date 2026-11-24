package com.sopilot.core.department;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** {@code core.departments}; every call needs the RLS context of the workspace (TECH §4.2). */
@Repository
public class DepartmentRepository {

    private final JdbcTemplate jdbc;

    public DepartmentRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(UUID id, UUID workspaceId, String name) {
        jdbc.update("INSERT INTO core.departments (id, workspace_id, name) VALUES (?, ?, ?)", id, workspaceId, name);
    }

    public Optional<Department> find(UUID workspaceId, UUID id) {
        return jdbc.query(SELECT + " WHERE workspace_id = ? AND id = ?", MAPPER, workspaceId, id)
                .stream().findFirst();
    }

    public List<Department> list(UUID workspaceId, boolean includeArchived) {
        return jdbc.query(SELECT + " WHERE workspace_id = ?" + (includeArchived ? "" : " AND status = 'ACTIVE'")
                + " ORDER BY lower(name), id", MAPPER, workspaceId);
    }

    public void update(UUID workspaceId, UUID id, String name, DepartmentStatus status) {
        jdbc.update("UPDATE core.departments SET name = ?, status = ? WHERE workspace_id = ? AND id = ?",
                name, status.name(), workspaceId, id);
    }

    public void delete(UUID workspaceId, UUID id) {
        jdbc.update("DELETE FROM core.departments WHERE workspace_id = ? AND id = ?", workspaceId, id);
    }

    public Usage usage(UUID workspaceId, UUID id) {
        return jdbc.queryForObject("SELECT "
                        + "(SELECT count(*) FROM core.memberships WHERE workspace_id = ? AND department_id = ?), "
                        + "(SELECT count(*) FROM core.invitations WHERE workspace_id = ? AND department_id = ? "
                        + "   AND accepted_at IS NULL AND revoked_at IS NULL), "
                        + "(SELECT count(*) FROM core.document_departments WHERE workspace_id = ? AND department_id = ?)",
                (rs, i) -> new Usage(rs.getLong(1), rs.getLong(2), rs.getLong(3)),
                workspaceId, id, workspaceId, id, workspaceId, id);
    }

    private static final String SELECT = "SELECT id, workspace_id, name, status, created_at, updated_at FROM core.departments";

    private static final org.springframework.jdbc.core.RowMapper<Department> MAPPER = (rs, i) -> new Department(
            rs.getObject("id", UUID.class), rs.getObject("workspace_id", UUID.class), rs.getString("name"),
            DepartmentStatus.valueOf(rs.getString("status")),
            rs.getObject("created_at", OffsetDateTime.class), rs.getObject("updated_at", OffsetDateTime.class));

    public enum DepartmentStatus { ACTIVE, ARCHIVED }

    public record Department(UUID id, UUID workspaceId, String name, DepartmentStatus status,
                             OffsetDateTime createdAt, OffsetDateTime updatedAt) {
    }

    public record Usage(long members, long pendingInvitations, long documents) {
        public boolean inUse() {
            return members > 0 || pendingInvitations > 0 || documents > 0;
        }
    }
}
