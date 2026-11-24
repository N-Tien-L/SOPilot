package com.sopilot.core.member;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * {@code core.invitations}. Admin-side calls need the RLS context of the workspace and filter
 * {@code workspace_id}. Redeeming goes through {@code core.accept_invitation}: the invitee is not a
 * member yet, so that function (SECURITY DEFINER, V008) is the only path that crosses workspaces.
 */
@Repository
public class InvitationRepository {

    private static final String SELECT = "SELECT i.id, i.email, i.role, i.display_name, i.employee_code, "
            + "i.job_title, i.department_id, d.name AS department_name, i.invited_by, i.expires_at, i.created_at "
            + "FROM core.invitations i LEFT JOIN core.departments d "
            + "ON d.workspace_id = i.workspace_id AND d.id = i.department_id";

    private static final RowMapper<Invitation> MAPPER = (rs, i) -> new Invitation(
            rs.getObject("id", UUID.class), rs.getString("email"), rs.getString("role"),
            rs.getString("display_name"), rs.getString("employee_code"), rs.getString("job_title"),
            rs.getObject("department_id", UUID.class), rs.getString("department_name"),
            rs.getObject("invited_by", UUID.class), rs.getObject("expires_at", OffsetDateTime.class),
            rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcTemplate jdbc;

    public InvitationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(UUID id, UUID workspaceId, String email, String role, String displayName,
                       String employeeCode, String jobTitle, UUID departmentId, byte[] tokenHash, UUID invitedBy,
                       OffsetDateTime expiresAt) {
        jdbc.update("INSERT INTO core.invitations (id, workspace_id, email, role, display_name, employee_code, "
                        + "job_title, department_id, token_hash, invited_by, expires_at) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                id, workspaceId, email, role, displayName, employeeCode, jobTitle, departmentId, tokenHash,
                invitedBy, expiresAt);
    }

    /** Pending and not expired, oldest first. */
    public List<Invitation> listPending(UUID workspaceId) {
        return jdbc.query(SELECT + " WHERE i.workspace_id = ? AND i.accepted_at IS NULL AND i.revoked_at IS NULL "
                + "AND i.expires_at > now() ORDER BY i.created_at, i.id", MAPPER, workspaceId);
    }

    /**
     * Frees the one-pending-per-email slot when the previous invitation expired unused: the unique index
     * ignores expiry, so without this an expired link would block inviting the same address again.
     */
    public int revokeExpiredFor(UUID workspaceId, String email) {
        return jdbc.update("UPDATE core.invitations SET revoked_at = now() WHERE workspace_id = ? AND email = ? "
                + "AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at <= now()", workspaceId, email);
    }

    /** Locks the row so a concurrent accept and revoke cannot both succeed. */
    public Optional<State> lockState(UUID workspaceId, UUID id) {
        return jdbc.query("SELECT accepted_at, revoked_at FROM core.invitations WHERE workspace_id = ? AND id = ? "
                        + "FOR UPDATE",
                (rs, i) -> new State(rs.getObject("accepted_at", OffsetDateTime.class) != null,
                        rs.getObject("revoked_at", OffsetDateTime.class) != null),
                workspaceId, id).stream().findFirst();
    }

    public void revoke(UUID workspaceId, UUID id) {
        jdbc.update("UPDATE core.invitations SET revoked_at = now() WHERE workspace_id = ? AND id = ? "
                + "AND accepted_at IS NULL AND revoked_at IS NULL", workspaceId, id);
    }

    public boolean memberEmailExists(UUID workspaceId, String email) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM core.memberships "
                + "WHERE workspace_id = ? AND email = ?)", Boolean.class, workspaceId, email));
    }

    public boolean pendingEmailExists(UUID workspaceId, String email) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM core.invitations "
                + "WHERE workspace_id = ? AND email = ? AND accepted_at IS NULL AND revoked_at IS NULL)",
                Boolean.class, workspaceId, email));
    }

    /** True when a member or another pending invitation already holds the code. */
    public boolean employeeCodeTaken(UUID workspaceId, String employeeCode) {
        return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS (SELECT 1 FROM core.memberships "
                + "WHERE workspace_id = ? AND employee_code = ?) OR EXISTS (SELECT 1 FROM core.invitations "
                + "WHERE workspace_id = ? AND employee_code = ? AND accepted_at IS NULL AND revoked_at IS NULL "
                + "AND expires_at > now())", Boolean.class, workspaceId, employeeCode, workspaceId, employeeCode));
    }

    /** Exactly one of {@code tokenHash} and {@code invitationId} must be set (the SQL function enforces it). */
    public Acceptance accept(UUID userId, byte[] tokenHash, UUID invitationId) {
        return jdbc.queryForObject("SELECT o_outcome, o_workspace_id, o_invitation_id, o_role, o_department_id, "
                        + "o_department_dropped FROM core.accept_invitation(?, ?, ?)",
                (rs, i) -> new Acceptance(rs.getString("o_outcome"), rs.getObject("o_workspace_id", UUID.class),
                        rs.getObject("o_invitation_id", UUID.class), rs.getString("o_role"),
                        rs.getObject("o_department_id", UUID.class), rs.getBoolean("o_department_dropped")),
                userId, tokenHash, invitationId);
    }

    public record Invitation(UUID id, String email, String role, String displayName, String employeeCode,
                             String jobTitle, UUID departmentId, String departmentName, UUID invitedBy,
                             OffsetDateTime expiresAt, OffsetDateTime createdAt) {
    }

    public record State(boolean accepted, boolean revoked) {
    }

    public record Acceptance(String outcome, UUID workspaceId, UUID invitationId, String role, UUID departmentId,
                             boolean departmentDropped) {
    }
}
