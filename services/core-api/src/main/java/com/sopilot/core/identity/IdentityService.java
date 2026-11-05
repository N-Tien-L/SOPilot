package com.sopilot.core.identity;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.identity.UserRepository.UserRecord;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.security.AccessTokenIssuer;
import com.sopilot.core.security.AccessTokenIssuer.IssuedToken;
import com.sopilot.core.tenancy.RlsContext;
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

    public IdentityService(JdbcTemplate jdbc, UserRepository users, ExternalIdentityRepository identities,
                           WorkspaceRepository workspaces, RlsContext rls, AccessTokenIssuer tokens) {
        this.jdbc = jdbc;
        this.users = users;
        this.identities = identities;
        this.workspaces = workspaces;
        this.rls = rls;
        this.tokens = tokens;
    }

    @Transactional
    public LoginResponse login(ExternalIdentityClaims identity) {
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

        IssuedToken token = tokens.issue(userId, workspaceId, membership.role().name(), membership.departmentId());
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
