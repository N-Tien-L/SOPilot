package com.sopilot.core.identity;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.identity.IdentityService.LoginSession;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.security.AccessTokenIssuer;
import com.sopilot.core.security.AccessTokenIssuer.IssuedToken;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.workspace.WorkspaceRepository;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipRecord;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import com.sopilot.core.workspace.WorkspaceService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.UUID;

/**
 * Moves a signed-in user into another workspace (TECH-V2-core-api §5.1, §5.2): checks the membership,
 * ends the refresh chain of the workspace being left, and issues an access token plus a fresh refresh
 * chain for the new one. Lives in {@code identity} because it issues tokens; the workspace rows
 * themselves are {@link WorkspaceService}.
 */
@Service
public class WorkspaceSessionService {

    private final WorkspaceService workspaceService;
    private final WorkspaceRepository workspaces;
    private final RefreshTokenService refresh;
    private final AccessTokenIssuer tokens;
    private final IdentityService identity;
    private final UserRepository users;
    private final TenantTx tenant;
    private final TransactionTemplate tx;

    public WorkspaceSessionService(WorkspaceService workspaceService, WorkspaceRepository workspaces,
                                   RefreshTokenService refresh, AccessTokenIssuer tokens, IdentityService identity,
                                   UserRepository users, TenantTx tenant, TransactionTemplate tx) {
        this.workspaceService = workspaceService;
        this.workspaces = workspaces;
        this.refresh = refresh;
        this.tokens = tokens;
        this.identity = identity;
        this.users = users;
        this.tenant = tenant;
        this.tx = tx;
    }

    /** {@code 404} when the user is not a member (or the workspace was deleted), {@code 403} when suspended. */
    public LoginSession switchTo(UUID userId, UUID workspaceId, String currentRefreshToken) {
        return tx.execute(status -> {
            MembershipRecord membership = tenant.run(workspaceId, userId,
                    () -> workspaces.findMembership(workspaceId, userId).orElse(null));
            if (membership == null) {
                throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Workspace not found.");
            }
            if (membership.status() != MembershipStatus.ACTIVE) {
                throw new ApiException(HttpStatus.FORBIDDEN, "MEMBERSHIP_SUSPENDED", "Your membership is suspended.");
            }
            return enter(userId, membership, currentRefreshToken);
        });
    }

    /** Creates a TEAM workspace owned by the caller and signs them into it. */
    public LoginSession createTeam(UUID userId, String name, String currentRefreshToken) {
        return tx.execute(status -> {
            UUID workspaceId = workspaceService.createTeam(userId, name);
            MembershipRecord membership = tenant.run(workspaceId, userId,
                    () -> workspaces.findMembership(workspaceId, userId)
                            .orElseThrow(() -> new IllegalStateException("New workspace has no membership")));
            return enter(userId, membership, currentRefreshToken);
        });
    }

    private LoginSession enter(UUID userId, MembershipRecord membership, String currentRefreshToken) {
        UUID workspaceId = membership.workspaceId();
        if (currentRefreshToken != null && !currentRefreshToken.isBlank()) {
            refresh.revokeChainOwnedBy(currentRefreshToken, userId, "LOGOUT");
        }
        users.setLastActiveWorkspace(userId, workspaceId);
        IssuedToken access = tokens.issue(userId, workspaceId, membership.role().name(), membership.departmentId());
        String newRefresh = refresh.start(userId, workspaceId);
        LoginResponse response = identity.describe(userId, workspaceId, access);
        return new LoginSession(response, newRefresh);
    }
}
