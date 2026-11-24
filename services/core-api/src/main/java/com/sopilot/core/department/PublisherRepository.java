package com.sopilot.core.department;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * {@code core.department_publishers} and {@code core.workspace_publishers} (ADR-009, TECH §15). Every call needs
 * the RLS context of the workspace and filters {@code workspace_id}. The {@code member} lookup reads
 * {@code core.memberships} itself because this package cannot depend on {@code workspace} or {@code member}
 * (module cycles, {@code ArchitectureTest}).
 *
 * <p>Locking: a document write takes {@code FOR SHARE} on the publisher row it relies on; changing the
 * publisher takes {@code FOR UPDATE} on the same row, so the old publisher cannot finish a write after
 * the change has committed.
 */
@Repository
public class PublisherRepository {

    private final JdbcTemplate jdbc;

    public PublisherRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** A membership as the write policy needs it: current role, status and department, straight from the table. */
    public record Member(UUID userId, String role, boolean active, UUID departmentId, String displayName) {
        public boolean isOwner() {
            return active && "OWNER".equals(role);
        }
    }

    public Optional<Member> member(UUID workspaceId, UUID userId) {
        return jdbc.query("SELECT user_id, role, status, department_id, display_name FROM core.memberships "
                        + "WHERE workspace_id = ? AND user_id = ?",
                (rs, i) -> new Member(rs.getObject("user_id", UUID.class), rs.getString("role"),
                        "ACTIVE".equals(rs.getString("status")), rs.getObject("department_id", UUID.class),
                        rs.getString("display_name")),
                workspaceId, userId).stream().findFirst();
    }

    /**
     * Like {@link #member} but locks the row {@code FOR SHARE} until the end of the transaction. Assigning a publisher
     * uses it so that a concurrent department change (which updates this row) either finishes first, and the
     * assignment then sees the new department, or waits until the assignment has committed and then removes the
     * publisher row it created. Without it the foreign key of {@code department_publishers} only takes a key lock,
     * which a non-key update does not wait for.
     */
    public Optional<Member> lockMemberShared(UUID workspaceId, UUID userId) {
        return jdbc.query("SELECT user_id, role, status, department_id, display_name FROM core.memberships "
                        + "WHERE workspace_id = ? AND user_id = ? FOR SHARE",
                (rs, i) -> new Member(rs.getObject("user_id", UUID.class), rs.getString("role"),
                        "ACTIVE".equals(rs.getString("status")), rs.getObject("department_id", UUID.class),
                        rs.getString("display_name")),
                workspaceId, userId).stream().findFirst();
    }

    // ---- reads for the policy -------------------------------------------------------------------

    /** The department's publisher, locked {@code FOR SHARE} until the end of the transaction. */
    public Optional<UUID> lockDepartmentPublisherShared(UUID workspaceId, UUID departmentId) {
        return jdbc.queryForList("SELECT user_id FROM core.department_publishers WHERE workspace_id = ? "
                + "AND department_id = ? FOR SHARE", UUID.class, workspaceId, departmentId).stream().findFirst();
    }

    public Optional<UUID> lockWorkspacePublisherShared(UUID workspaceId) {
        return jdbc.queryForList("SELECT user_id FROM core.workspace_publishers WHERE workspace_id = ? FOR SHARE",
                UUID.class, workspaceId).stream().findFirst();
    }

    /** What the caller publishes, without locking: only decides which admin fields a view shows. */
    public boolean isWorkspacePublisher(UUID workspaceId, UUID userId) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM core.workspace_publishers "
                + "WHERE workspace_id = ? AND user_id = ?)", Boolean.class, workspaceId, userId));
    }

    public List<UUID> departmentsPublishedBy(UUID workspaceId, UUID userId) {
        return jdbc.queryForList("SELECT department_id FROM core.department_publishers WHERE workspace_id = ? "
                + "AND user_id = ? ORDER BY department_id", UUID.class, workspaceId, userId);
    }

    // ---- listing --------------------------------------------------------------------------------

    public record PublisherRef(UUID userId, String displayName) {
    }

    public record DepartmentPublisher(UUID departmentId, String name, PublisherRef publisher) {
    }

    public Optional<PublisherRef> workspacePublisher(UUID workspaceId) {
        return jdbc.query("SELECT p.user_id, m.display_name FROM core.workspace_publishers p "
                        + "JOIN core.memberships m ON m.workspace_id = p.workspace_id AND m.user_id = p.user_id "
                        + "WHERE p.workspace_id = ?",
                (rs, i) -> new PublisherRef(rs.getObject("user_id", UUID.class), rs.getString("display_name")),
                workspaceId).stream().findFirst();
    }

    public List<DepartmentPublisher> departmentPublishers(UUID workspaceId, boolean includeArchived) {
        return jdbc.query("SELECT d.id, d.name, p.user_id, m.display_name FROM core.departments d "
                        + "LEFT JOIN core.department_publishers p "
                        + "  ON p.workspace_id = d.workspace_id AND p.department_id = d.id "
                        + "LEFT JOIN core.memberships m ON m.workspace_id = p.workspace_id AND m.user_id = p.user_id "
                        + "WHERE d.workspace_id = ?" + (includeArchived ? "" : " AND d.status = 'ACTIVE'")
                        + " ORDER BY lower(d.name), d.id",
                (rs, i) -> new DepartmentPublisher(rs.getObject("id", UUID.class), rs.getString("name"),
                        rs.getObject("user_id", UUID.class) == null ? null
                                : new PublisherRef(rs.getObject("user_id", UUID.class), rs.getString("display_name"))),
                workspaceId);
    }

    // ---- writes (OWNER API, member changes) ------------------------------------------------------

    /** Locks the row {@code FOR UPDATE}; empty when the department has no publisher. */
    public Optional<UUID> lockDepartmentPublisher(UUID workspaceId, UUID departmentId) {
        return jdbc.queryForList("SELECT user_id FROM core.department_publishers WHERE workspace_id = ? "
                + "AND department_id = ? FOR UPDATE", UUID.class, workspaceId, departmentId).stream().findFirst();
    }

    public Optional<UUID> lockWorkspacePublisher(UUID workspaceId) {
        return jdbc.queryForList("SELECT user_id FROM core.workspace_publishers WHERE workspace_id = ? FOR UPDATE",
                UUID.class, workspaceId).stream().findFirst();
    }

    public void putDepartmentPublisher(UUID workspaceId, UUID departmentId, UUID userId) {
        jdbc.update("INSERT INTO core.department_publishers (workspace_id, department_id, user_id) VALUES (?, ?, ?) "
                + "ON CONFLICT (department_id) DO UPDATE SET user_id = EXCLUDED.user_id, assigned_at = now()",
                workspaceId, departmentId, userId);
    }

    public void putWorkspacePublisher(UUID workspaceId, UUID userId) {
        jdbc.update("INSERT INTO core.workspace_publishers (workspace_id, user_id) VALUES (?, ?) "
                + "ON CONFLICT (workspace_id) DO UPDATE SET user_id = EXCLUDED.user_id, assigned_at = now()",
                workspaceId, userId);
    }

    public void deleteDepartmentPublisher(UUID workspaceId, UUID departmentId) {
        jdbc.update("DELETE FROM core.department_publishers WHERE workspace_id = ? AND department_id = ?",
                workspaceId, departmentId);
    }

    public void deleteWorkspacePublisher(UUID workspaceId) {
        jdbc.update("DELETE FROM core.workspace_publishers WHERE workspace_id = ?", workspaceId);
    }

    /**
     * A member who moves to another department stops publishing for the old one (ADR-009, TECH §15.3).
     * Returns the departments they no longer publish.
     */
    public List<UUID> deleteDepartmentPublishingExcept(UUID workspaceId, UUID userId, UUID keepDepartmentId) {
        return jdbc.queryForList("DELETE FROM core.department_publishers WHERE workspace_id = ? AND user_id = ? "
                + "AND department_id IS DISTINCT FROM ? RETURNING department_id", UUID.class,
                workspaceId, userId, keepDepartmentId);
    }

    /** Is the document's publishing scope served by someone? Used only to tell the OWNER after a transfer. */
    public boolean hasDepartmentPublisher(UUID workspaceId, UUID departmentId) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM core.department_publishers "
                + "WHERE workspace_id = ? AND department_id = ?)", Boolean.class, workspaceId, departmentId));
    }

    public boolean hasWorkspacePublisher(UUID workspaceId) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM core.workspace_publishers "
                + "WHERE workspace_id = ?)", Boolean.class, workspaceId));
    }
}
