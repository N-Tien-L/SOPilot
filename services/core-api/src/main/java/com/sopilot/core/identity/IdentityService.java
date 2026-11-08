package com.sopilot.core.identity;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.identity.UserRepository.UserRecord;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.security.AccessTokenIssuer;
import com.sopilot.core.security.AccessTokenIssuer.IssuedToken;
import com.sopilot.core.tenancy.RlsContext;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.workspace.WorkspaceRepository;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipRecord;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import com.sopilot.core.workspace.WorkspaceRepository.WorkspaceRecord;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowCallbackHandler;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

/**
 * Login and just-in-time provisioning (FR-01, FR-02; TECH-V2-core-api §2.1).
 * Identity is {@code (issuer, subject)}. First login creates the user, the identity link, a
 * PERSONAL workspace and the OWNER membership in one transaction; repeated or concurrent logins
 * reuse them. The access token is bound to the PERSONAL workspace; workspace selection, refresh
 * cookies and invitations arrive in V2-29/V2-30.
 */
@Service
public class IdentityService {

    private static final RowCallbackHandler IGNORE = rs -> { };
    private static final int MAX_WORKSPACE_NAME = 100;

    private final JdbcTemplate jdbc;
    private final UserRepository users;
    private final ExternalIdentityRepository identities;
    private final WorkspaceRepository workspaces;
    private final RlsContext rls;
    private final AccessTokenIssuer tokens;
    private final AuditService audit;
    private final RefreshTokenService refresh;
    private final TenantTx tenant;

    public IdentityService(JdbcTemplate jdbc, UserRepository users, ExternalIdentityRepository identities,
                           WorkspaceRepository workspaces, RlsContext rls, AccessTokenIssuer tokens,
                           AuditService audit, RefreshTokenService refresh, TenantTx tenant) {
        this.jdbc = jdbc;
        this.users = users;
        this.identities = identities;
        this.workspaces = workspaces;
        this.rls = rls;
        this.tokens = tokens;
        this.audit = audit;
        this.refresh = refresh;
        this.tenant = tenant;
    }

    /** A login together with the first refresh token of its chain (sent only as an HttpOnly cookie). */
    public record LoginSession(LoginResponse response, String refreshToken) {
        @Override
        public String toString() {
            return "LoginSession[response=" + response + ", refreshToken=<redacted>]";
        }
    }

    /** Login without a refresh chain; the browser flow uses {@link #loginWithSession}. */
    @Transactional
    public LoginResponse login(ExternalIdentityClaims identity) {
        return authenticate(identity).response();
    }

    @Transactional
    public LoginSession loginWithSession(ExternalIdentityClaims identity) {
        Authenticated a = authenticate(identity);
        return new LoginSession(a.response(), refresh.start(a.userId(), a.workspaceId()));
    }

    /**
     * The login payload for a user already authenticated into {@code workspaceId} (refresh, switch,
     * create workspace). The caller has verified the membership; this only reads display fields.
     */
    public LoginResponse describe(UUID userId, UUID workspaceId, IssuedToken token) {
        return tenant.run(workspaceId, userId, () -> {
            UserRecord user = users.findById(userId).orElseThrow(() -> new IllegalStateException("User row is missing"));
            WorkspaceRecord workspace = workspaces.findVisible(workspaceId)
                    .orElseThrow(() -> new IllegalStateException("Workspace is not visible"));
            MembershipRecord membership = workspaces.findMembership(workspaceId, userId)
                    .orElseThrow(() -> new IllegalStateException("Membership is missing"));
            return response(token, user, workspace, membership);
        });
    }

    private record Authenticated(LoginResponse response, UUID userId, UUID workspaceId) {
    }

    private Authenticated authenticate(ExternalIdentityClaims identity) {
        // Serialize concurrent first logins of the same identity; released at commit/rollback.
        jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", IGNORE,
                "identity:" + identity.issuer() + "\n" + identity.subject());

        UUID userId = identities.findUserId(identity.issuer(), identity.subject())
                .orElseGet(() -> provisionUser(identity));
        if (identity.hostedDomain() != null) {
            identities.updateHostedDomain(identity.issuer(), identity.subject(), identity.hostedDomain());
        }
        UserRecord user = users.findById(userId)
                .orElseThrow(() -> new IllegalStateException("Linked user row is missing"));

        UUID workspaceId = workspaces.ensurePersonalWorkspace(
                userId, UuidV7.generate(), personalWorkspaceName(user), user.email());

        rls.bind(workspaceId, userId);
        MembershipRecord membership = workspaces.findMembership(workspaceId, userId)
                .orElseThrow(() -> new IllegalStateException("Personal workspace has no membership"));
        if (membership.status() != MembershipStatus.ACTIVE) {
            throw new ApiException(HttpStatus.FORBIDDEN, "MEMBERSHIP_SUSPENDED", "Your membership is suspended.");
        }
        WorkspaceRecord workspace = workspaces.findVisible(workspaceId)
                .orElseThrow(() -> new IllegalStateException("Personal workspace is not visible"));
        users.setLastActiveWorkspace(userId, workspaceId);
        audit.record(workspaceId, userId, "LOGIN", "USER", userId, java.util.Map.of());

        IssuedToken token = tokens.issue(userId, workspaceId, membership.role().name(), membership.departmentId());
        return new Authenticated(response(token, user, workspace, membership), userId, workspaceId);
    }

    private static LoginResponse response(IssuedToken token, UserRecord user, WorkspaceRecord workspace,
                                          MembershipRecord membership) {
        return new LoginResponse(
                token.value(),
                token.expiresInSeconds(),
                new LoginResponse.UserView(user.id(), user.email(), user.displayName()),
                new LoginResponse.WorkspaceView(workspace.id(), workspace.name(), workspace.kind().name(),
                        membership.role().name()),
                List.of());
    }

    private UUID provisionUser(ExternalIdentityClaims identity) {
        UUID userId = UuidV7.generate();
        users.insert(userId, identity.email(), identity.displayName(), identity.avatarUrl());
        if (!identities.insertIfAbsent(UuidV7.generate(), userId, identity.issuer(), identity.subject(),
                identity.email(), identity.hostedDomain())) {
            // Unreachable while the advisory lock is held; fail rather than leave an orphan user.
            throw new IllegalStateException("External identity was linked concurrently");
        }
        return userId;
    }

    static String personalWorkspaceName(UserRecord user) {
        String base = user.displayName() != null && !user.displayName().isBlank()
                ? user.displayName().trim()
                : user.email().split("@")[0];
        String name = base + "'s workspace";
        return name.length() <= MAX_WORKSPACE_NAME ? name : name.substring(0, MAX_WORKSPACE_NAME).trim();
    }
}
