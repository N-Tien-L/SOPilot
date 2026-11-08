package com.sopilot.core.identity;

import com.sopilot.core.common.UuidV7;
import com.sopilot.core.config.SopilotProperties;
import com.sopilot.core.identity.RefreshTokenRepository.StoredToken;
import com.sopilot.core.security.AccessTokenIssuer;
import com.sopilot.core.security.AccessTokenIssuer.IssuedToken;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.workspace.WorkspaceRepository;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipRecord;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.Optional;
import java.util.UUID;

/**
 * Refresh-token chains (TECH-V2-core-api §5.1). A token is 256 random bits, stored only as its
 * SHA-256. Each use exchanges it for the next token of the same family; presenting a token that was
 * already exchanged or revoked is replay, and revokes the whole family. The membership is re-read on
 * every refresh, so a removed or suspended member loses the session at the next refresh and the new
 * access token carries the role and department as they are now (ADR-007 §4.5).
 * Tokens, hashes and cookie values are never logged.
 */
@Service
public class RefreshTokenService {

    private static final SecureRandom RANDOM = new SecureRandom();

    private final RefreshTokenRepository repository;
    private final WorkspaceRepository workspaces;
    private final AccessTokenIssuer tokens;
    private final TenantTx tenant;
    private final TransactionTemplate tx;
    private final Duration ttl;

    public RefreshTokenService(RefreshTokenRepository repository, WorkspaceRepository workspaces,
                               AccessTokenIssuer tokens, TenantTx tenant, TransactionTemplate tx,
                               SopilotProperties properties) {
        this.repository = repository;
        this.workspaces = workspaces;
        this.tokens = tokens;
        this.tenant = tenant;
        this.tx = tx;
        this.ttl = properties.auth().refreshTtl();
    }

    public Duration ttl() {
        return ttl;
    }

    /** Starts a new chain and returns its first token. Call inside the transaction of the login or switch. */
    public String start(UUID userId, UUID workspaceId) {
        return insert(userId, workspaceId, UuidV7.generate());
    }

    /** Exchanges a presented token for the next one, or says why it cannot be. */
    public Rotation rotate(String presented) {
        byte[] hash = hash(presented);
        return tx.execute(status -> {
            Optional<StoredToken> found = repository.lockByHash(hash);
            if (found.isEmpty() || found.get().expiresAt().isBefore(now())) {
                return Rotation.rejected(HttpStatus.UNAUTHORIZED, "UNAUTHENTICATED", "Sign in to continue.");
            }
            StoredToken token = found.get();
            if (token.used() || token.revoked()) {
                repository.revokeFamily(token.familyId(), "REUSE_DETECTED");
                return Rotation.rejected(HttpStatus.UNAUTHORIZED, "UNAUTHENTICATED", "Sign in to continue.");
            }
            MembershipRecord membership = tenant.run(token.workspaceId(), token.userId(),
                    () -> workspaces.findMembership(token.workspaceId(), token.userId()).orElse(null));
            if (membership == null) {
                repository.revokeFamily(token.familyId(), "MEMBERSHIP_LOST");
                return Rotation.rejected(HttpStatus.UNAUTHORIZED, "MEMBERSHIP_LOST",
                        "You are no longer a member of this workspace.");
            }
            if (membership.status() != MembershipStatus.ACTIVE) {
                repository.revokeFamily(token.familyId(), "SUSPENDED");
                return Rotation.rejected(HttpStatus.FORBIDDEN, "MEMBERSHIP_SUSPENDED", "Your membership is suspended.");
            }
            repository.markUsed(token.id());
            String next = insert(token.userId(), token.workspaceId(), token.familyId());
            IssuedToken access = tokens.issue(token.userId(), token.workspaceId(), membership.role().name(),
                    membership.departmentId());
            return Rotation.ok(token.userId(), token.workspaceId(), next, access);
        });
    }

    /** Revokes the chain of a presented token; unknown tokens are ignored. Returns the owner if it was found. */
    public Optional<UUID> revokeChain(String presented, String reason) {
        byte[] hash = hash(presented);
        return tx.execute(status -> repository.lockByHash(hash).map(token -> {
            repository.revokeFamily(token.familyId(), reason);
            return token.userId();
        }));
    }

    /** Like {@link #revokeChain} but only when the token belongs to {@code userId}; joins the caller's transaction. */
    public void revokeChainOwnedBy(String presented, UUID userId, String reason) {
        byte[] hash = hash(presented);
        tx.executeWithoutResult(status -> repository.lockByHash(hash)
                .filter(token -> token.userId().equals(userId))
                .ifPresent(token -> repository.revokeFamily(token.familyId(), reason)));
    }

    /** Ends every session of one membership. Call inside the transaction of the change that caused it. */
    public void revokeForMembership(UUID userId, UUID workspaceId, String reason) {
        repository.revokeForMembership(userId, workspaceId, reason);
    }

    /** Ends every session issued for a workspace. */
    public void revokeForWorkspace(UUID workspaceId, String reason) {
        repository.revokeForWorkspace(workspaceId, reason);
    }

    private String insert(UUID userId, UUID workspaceId, UUID familyId) {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        String raw = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        repository.insert(UuidV7.generate(), userId, workspaceId, familyId, hash(raw), now().plus(ttl));
        return raw;
    }

    private static OffsetDateTime now() {
        return OffsetDateTime.now(ZoneOffset.UTC);
    }

    static byte[] hash(String token) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.US_ASCII));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable");
        }
    }

    /** Result of {@link #rotate}; {@code refreshToken} and {@code access} are secrets. */
    public record Rotation(boolean accepted, UUID userId, UUID workspaceId, String refreshToken, IssuedToken access,
                           HttpStatus status, String code, String message) {

        static Rotation ok(UUID userId, UUID workspaceId, String refreshToken, IssuedToken access) {
            return new Rotation(true, userId, workspaceId, refreshToken, access, null, null, null);
        }

        static Rotation rejected(HttpStatus status, String code, String message) {
            return new Rotation(false, null, null, null, null, status, code, message);
        }

        @Override
        public String toString() {
            return "Rotation[accepted=" + accepted + ", code=" + code + "]";
        }
    }
}
