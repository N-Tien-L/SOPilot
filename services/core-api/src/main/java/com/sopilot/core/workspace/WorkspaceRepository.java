package com.sopilot.core.workspace;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

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
        return jdbc.query("SELECT id, name, kind FROM core.workspaces WHERE id = ?",
                (rs, i) -> new WorkspaceRecord(rs.getObject("id", UUID.class), rs.getString("name"),
                        WorkspaceKind.valueOf(rs.getString("kind"))),
                workspaceId).stream().findFirst();
    }

    /** Requires the RLS context of this workspace or of this user. */
    public Optional<MembershipRecord> findMembership(UUID workspaceId, UUID userId) {
        return jdbc.query("SELECT workspace_id, user_id, role, status, department_id FROM core.memberships "
                        + "WHERE workspace_id = ? AND user_id = ?",
                (rs, i) -> new MembershipRecord(rs.getObject("workspace_id", UUID.class),
                        rs.getObject("user_id", UUID.class),
                        WorkspaceRole.valueOf(rs.getString("role")),
                        MembershipStatus.valueOf(rs.getString("status")),
                        rs.getObject("department_id", UUID.class)),
                workspaceId, userId).stream().findFirst();
    }

    public enum WorkspaceKind { PERSONAL, TEAM }

    public enum WorkspaceRole { OWNER, ADMIN, MEMBER }

    public enum MembershipStatus { ACTIVE, SUSPENDED }

    public record WorkspaceRecord(UUID id, String name, WorkspaceKind kind) {
    }

    public record MembershipRecord(UUID workspaceId, UUID userId, WorkspaceRole role, MembershipStatus status,
                                   UUID departmentId) {
    }
}
