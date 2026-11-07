package com.sopilot.core.member;

import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import com.sopilot.core.workspace.WorkspaceRepository.WorkspaceRole;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * {@code core.memberships} of one workspace. The membership RLS policy also exposes the caller's own
 * rows in other workspaces, so every query here filters {@code workspace_id} explicitly.
 */
@Repository
public class MemberRepository {

    private static final String SELECT = "SELECT m.user_id, m.email, m.display_name, m.employee_code, m.job_title, "
            + "m.role, m.status, m.department_id, d.name AS department_name, m.joined_at "
            + "FROM core.memberships m LEFT JOIN core.departments d "
            + "ON d.workspace_id = m.workspace_id AND d.id = m.department_id";

    private static final RowMapper<Member> MAPPER = (rs, i) -> new Member(
            rs.getObject("user_id", UUID.class), rs.getString("email"), rs.getString("display_name"),
            rs.getString("employee_code"), rs.getString("job_title"),
            WorkspaceRole.valueOf(rs.getString("role")), MembershipStatus.valueOf(rs.getString("status")),
            rs.getObject("department_id", UUID.class), rs.getString("department_name"),
            rs.getObject("joined_at", OffsetDateTime.class));

    private final JdbcTemplate jdbc;

    public MemberRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Member> find(UUID workspaceId, UUID userId) {
        return jdbc.query(SELECT + " WHERE m.workspace_id = ? AND m.user_id = ?", MAPPER, workspaceId, userId)
                .stream().findFirst();
    }

    public List<Member> search(UUID workspaceId, MembershipStatus status, UUID departmentId, String query) {
        StringBuilder sql = new StringBuilder(SELECT + " WHERE m.workspace_id = ?");
        List<Object> args = new ArrayList<>(List.of(workspaceId));
        if (status != null) {
            sql.append(" AND m.status = ?");
            args.add(status.name());
        }
        if (departmentId != null) {
            sql.append(" AND m.department_id = ?");
            args.add(departmentId);
        }
        if (query != null && !query.isBlank()) {
            sql.append(" AND (m.email ILIKE ? ESCAPE '\\' OR m.display_name ILIKE ? ESCAPE '\\' "
                    + "OR m.employee_code ILIKE ? ESCAPE '\\')");
            String like = "%" + query.trim().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%";
            args.add(like);
            args.add(like);
            args.add(like);
        }
        sql.append(" ORDER BY lower(coalesce(m.display_name, m.email)), m.user_id");
        return jdbc.query(sql.toString(), MAPPER, args.toArray());
    }

    /** Locks the active OWNER rows so concurrent demotions/removals cannot both pass the last-owner check. */
    public List<UUID> lockActiveOwners(UUID workspaceId) {
        return jdbc.queryForList("SELECT user_id FROM core.memberships WHERE workspace_id = ? AND role = 'OWNER' "
                + "AND status = 'ACTIVE' ORDER BY user_id FOR UPDATE", UUID.class, workspaceId);
    }

    public void updateProfile(UUID workspaceId, UUID userId, String displayName, String employeeCode,
                              String jobTitle, UUID departmentId) {
        jdbc.update("UPDATE core.memberships SET display_name = ?, employee_code = ?, job_title = ?, "
                        + "department_id = ? WHERE workspace_id = ? AND user_id = ?",
                displayName, employeeCode, jobTitle, departmentId, workspaceId, userId);
    }

    public void setSuspended(UUID workspaceId, UUID userId, boolean suspended) {
        jdbc.update("UPDATE core.memberships SET status = ?, suspended_at = "
                        + (suspended ? "now()" : "NULL") + " WHERE workspace_id = ? AND user_id = ?",
                suspended ? "SUSPENDED" : "ACTIVE", workspaceId, userId);
    }

    public void delete(UUID workspaceId, UUID userId) {
        jdbc.update("DELETE FROM core.memberships WHERE workspace_id = ? AND user_id = ?", workspaceId, userId);
    }

    public Optional<String> workspaceKind(UUID workspaceId) {
        return jdbc.queryForList("SELECT kind FROM core.workspaces WHERE id = ?", String.class, workspaceId)
                .stream().findFirst();
    }

    public record Member(UUID userId, String email, String displayName, String employeeCode, String jobTitle,
                         WorkspaceRole role, MembershipStatus status, UUID departmentId, String departmentName,
                         OffsetDateTime joinedAt) {
    }
}
