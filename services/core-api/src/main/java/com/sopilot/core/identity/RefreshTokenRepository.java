package com.sopilot.core.identity;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

/**
 * {@code core.refresh_tokens}: global, no RLS (TECH §3.1). Only the SHA-256 of the token is stored.
 * Callers run these inside one transaction; {@link #lockByHash} takes the row lock that serializes
 * concurrent use of the same token.
 */
@Repository
public class RefreshTokenRepository {

    private final JdbcTemplate jdbc;

    public RefreshTokenRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(UUID id, UUID userId, UUID workspaceId, UUID familyId, byte[] tokenHash,
                       OffsetDateTime expiresAt) {
        jdbc.update("INSERT INTO core.refresh_tokens (id, user_id, target_workspace_id, family_id, token_hash, expires_at) "
                + "VALUES (?, ?, ?, ?, ?, ?)", id, userId, workspaceId, familyId, tokenHash, expiresAt);
    }

    /** {@code grace} is the window measured on the database clock, the one that wrote {@code used_at}. */
    public Optional<StoredToken> lockByHash(byte[] tokenHash, java.time.Duration grace) {
        return jdbc.query("SELECT id, user_id, target_workspace_id, family_id, expires_at, used_at, revoked_at, "
                        + "successor_id, (used_at IS NOT NULL AND used_at > now() - make_interval(secs => ?)) AS in_grace "
                        + "FROM core.refresh_tokens WHERE token_hash = ? FOR UPDATE",
                (rs, i) -> new StoredToken(rs.getObject("id", UUID.class), rs.getObject("user_id", UUID.class),
                        rs.getObject("target_workspace_id", UUID.class), rs.getObject("family_id", UUID.class),
                        rs.getObject("expires_at", OffsetDateTime.class),
                        rs.getObject("used_at", OffsetDateTime.class),
                        rs.getObject("revoked_at", OffsetDateTime.class) != null,
                        rs.getObject("successor_id", UUID.class), rs.getBoolean("in_grace")),
                grace.toMillis() / 1000.0, tokenHash).stream().findFirst();
    }

    public Optional<StoredToken> lockByHash(byte[] tokenHash) {
        return lockByHash(tokenHash, java.time.Duration.ZERO);
    }

    /** Marks a token as exchanged and records the token issued in exchange. */
    public void markUsed(UUID id, UUID successorId) {
        jdbc.update("UPDATE core.refresh_tokens SET used_at = now(), successor_id = ? WHERE id = ?", successorId, id);
    }

    /**
     * Locks a token row and says whether it is still untouched (not used, not revoked). Empty when it is gone.
     * Always taken after the predecessor's lock, so concurrent grace refreshes serialize on the predecessor.
     */
    public Optional<Boolean> lockUnused(UUID id) {
        return jdbc.query("SELECT used_at IS NULL AND revoked_at IS NULL AS unused FROM core.refresh_tokens "
                + "WHERE id = ? FOR UPDATE", (rs, i) -> rs.getBoolean("unused"), id).stream().findFirst();
    }

    /** Retires a token that was never delivered: it counts as used, so presenting it later is replay. */
    public void retire(UUID id) {
        jdbc.update("UPDATE core.refresh_tokens SET used_at = now() WHERE id = ? AND used_at IS NULL", id);
    }

    /** Clears the successor pointer of an exchanged token once its grace was spent. */
    public void clearSuccessor(UUID id) {
        jdbc.update("UPDATE core.refresh_tokens SET successor_id = NULL WHERE id = ?", id);
    }

    /** Revokes every still-live token of the chain. */
    public void revokeFamily(UUID familyId, String reason) {
        jdbc.update("UPDATE core.refresh_tokens SET revoked_at = now(), revoked_reason = ? "
                + "WHERE family_id = ? AND revoked_at IS NULL", reason, familyId);
    }

    /** Revokes every chain of one membership (suspend, remove, leave, workspace delete). */
    public int revokeForMembership(UUID userId, UUID workspaceId, String reason) {
        return jdbc.update("UPDATE core.refresh_tokens SET revoked_at = now(), revoked_reason = ? "
                + "WHERE user_id = ? AND target_workspace_id = ? AND revoked_at IS NULL", reason, userId, workspaceId);
    }

    /** Revokes every chain issued for a workspace (workspace delete). */
    public int revokeForWorkspace(UUID workspaceId, String reason) {
        return jdbc.update("UPDATE core.refresh_tokens SET revoked_at = now(), revoked_reason = ? "
                + "WHERE target_workspace_id = ? AND revoked_at IS NULL", reason, workspaceId);
    }

    public record StoredToken(UUID id, UUID userId, UUID workspaceId, UUID familyId, OffsetDateTime expiresAt,
                              OffsetDateTime usedAt, boolean revoked, UUID successorId, boolean inGrace) {

        public boolean used() {
            return usedAt != null;
        }
    }
}
