package com.sopilot.core.workspace;

import com.sopilot.core.security.WorkspaceRole;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** {@code core.workspaces} and {@code core.memberships}; both are under RLS (TECH §4.2). */
@Repository
public class WorkspaceRepository {

    private final JdbcTemplate jdbc;

    public WorkspaceRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * Idempotent JIT through the {@code SECURITY DEFINER} helper: returns the user's PERSONAL
     * workspace, creating it and the OWNER membership on first call.
     */
    public UUID ensurePersonalWorkspace(UUID userId, UUID newWorkspaceId, String name, String email) {
        return jdbc.queryForObject("SELECT core.create_personal_workspace(?, ?, ?, ?)",
                UUID.class, userId, newWorkspaceId, name, email);
    }

    /** Requires the RLS context of this workspace or of a member. */
    public Optional<WorkspaceRecord> findVisible(UUID workspaceId) {
        return jdbc.query("SELECT id, name, kind FROM core.workspaces WHERE id = ? AND deleted_at IS NULL",
                (rs, i) -> new WorkspaceRecord(rs.getObject("id", UUID.class), rs.getString("name"),
                        WorkspaceKind.valueOf(rs.getString("kind"))),
                workspaceId).stream().findFirst();
    }

    /** Requires the RLS context of this workspace or of this user. */
    public Optional<MembershipRecord> findMembership(UUID workspaceId, UUID userId) {
        // A soft-deleted workspace has no usable membership: sessions into it end at the next refresh.
        return jdbc.query("SELECT m.workspace_id, m.user_id, m.role, m.status, m.department_id FROM core.memberships m "
                        + "JOIN core.workspaces w ON w.id = m.workspace_id AND w.deleted_at IS NULL "
                        + "WHERE m.workspace_id = ? AND m.user_id = ?",
                (rs, i) -> new MembershipRecord(rs.getObject("workspace_id", UUID.class),
                        rs.getObject("user_id", UUID.class),
                        WorkspaceRole.valueOf(rs.getString("role")),
                        MembershipStatus.valueOf(rs.getString("status")),
                        rs.getObject("department_id", UUID.class)),
                workspaceId, userId).stream().findFirst();
    }

    /**
     * Workspaces the user belongs to (any membership status), newest membership last. Filtered by
     * {@code user_id}: this is the one query that spans workspaces, and RLS shows only own memberships.
     */
    public List<WorkspaceSummary> listForUser(UUID userId) {
        return jdbc.query("SELECT w.id, w.name, w.kind, m.role, m.status FROM core.memberships m "
                        + "JOIN core.workspaces w ON w.id = m.workspace_id AND w.deleted_at IS NULL "
                        + "WHERE m.user_id = ? ORDER BY w.kind, m.joined_at, w.id",
                (rs, i) -> new WorkspaceSummary(rs.getObject("id", UUID.class), rs.getString("name"),
                        WorkspaceKind.valueOf(rs.getString("kind")), WorkspaceRole.valueOf(rs.getString("role")),
                        MembershipStatus.valueOf(rs.getString("status"))),
                userId);
    }

    /** Email and display name of a user, for the first membership row of a new workspace. */
    public Optional<UserProfile> findUserProfile(UUID userId) {
        return jdbc.query("SELECT email, display_name FROM core.users WHERE id = ?",
                (rs, i) -> new UserProfile(rs.getString("email"), rs.getString("display_name")), userId)
                .stream().findFirst();
    }

    /** Requires the RLS context of the new workspace (WITH CHECK {@code id = current_workspace()}). */
    public void insertTeamWorkspace(UUID id, String name, UUID createdBy) {
        jdbc.update("INSERT INTO core.workspaces (id, name, kind, created_by) VALUES (?, ?, 'TEAM', ?)",
                id, name, createdBy);
    }

    public void insertOwnerMembership(UUID workspaceId, UUID userId, String email, String displayName) {
        jdbc.update("INSERT INTO core.memberships (workspace_id, user_id, role, status, display_name, email) "
                + "VALUES (?, ?, 'OWNER', 'ACTIVE', ?, lower(?))", workspaceId, userId, displayName, email);
    }

    public int rename(UUID workspaceId, String name) {
        return jdbc.update("UPDATE core.workspaces SET name = ? WHERE id = ? AND deleted_at IS NULL",
                name, workspaceId);
    }

    public int softDelete(UUID workspaceId) {
        return jdbc.update("UPDATE core.workspaces SET deleted_at = now() WHERE id = ? AND deleted_at IS NULL",
                workspaceId);
    }

    public enum WorkspaceKind { PERSONAL, TEAM }

    public enum MembershipStatus { ACTIVE, SUSPENDED }

    public record WorkspaceRecord(UUID id, String name, WorkspaceKind kind) {
    }

    public record WorkspaceSummary(UUID id, String name, WorkspaceKind kind, WorkspaceRole role,
                                   MembershipStatus status) {
    }

    public record UserProfile(String email, String displayName) {
    }

    public record MembershipRecord(UUID workspaceId, UUID userId, WorkspaceRole role, MembershipStatus status,
                                   UUID departmentId) {
    }
}
