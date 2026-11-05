package com.sopilot.core.identity;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/** {@code core.users}: global, no RLS. core-api is the only writer (TECH §0). */
@Repository
public class UserRepository {

    private static final RowMapper<UserRecord> MAPPER = (rs, i) -> new UserRecord(
            rs.getObject("id", UUID.class),
            rs.getString("email"),
            rs.getString("display_name"),
            rs.getString("avatar_url"),
            rs.getObject("last_active_workspace_id", UUID.class));

    private final JdbcTemplate jdbc;

    public UserRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(UUID id, String email, String displayName, String avatarUrl) {
        jdbc.update("INSERT INTO core.users (id, email, display_name, avatar_url) VALUES (?, ?, ?, ?)",
                id, email, displayName, avatarUrl);
    }

    public Optional<UserRecord> findById(UUID id) {
        return jdbc.query("SELECT id, email, display_name, avatar_url, last_active_workspace_id FROM core.users WHERE id = ?",
                MAPPER, id).stream().findFirst();
    }

    public void setLastActiveWorkspace(UUID userId, UUID workspaceId) {
        jdbc.update("UPDATE core.users SET last_active_workspace_id = ? WHERE id = ? "
                + "AND last_active_workspace_id IS DISTINCT FROM ?", workspaceId, userId, workspaceId);
    }

    public record UserRecord(UUID id, String email, String displayName, String avatarUrl, UUID lastActiveWorkspaceId) {
    }
}
