package com.sopilot.core.identity;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.security.AccessTokenIssuer;
import com.sopilot.core.security.AccessTokenIssuer.IssuedToken;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.workspace.WorkspaceRepository;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipRecord;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.UUID;

/**
 * Issues a new access token for {@code (user, workspace)} from the membership as it is now
 * (ADR-007 §4.5): a removed member gets {@code 401 MEMBERSHIP_LOST}, a suspended one
 * {@code 403 MEMBERSHIP_SUSPENDED}, and role and department ({@code wdept}) are re-read from the
 * database. Refresh-cookie rotation and replay detection (V2-29) call this after validating their
 * own token; it holds no session state itself.
 */
@Service
public class SessionTokenService {

    private final WorkspaceRepository workspaces;
    private final AccessTokenIssuer tokens;
    private final TenantTx tenant;

    public SessionTokenService(WorkspaceRepository workspaces, AccessTokenIssuer tokens, TenantTx tenant) {
        this.workspaces = workspaces;
        this.tokens = tokens;
        this.tenant = tenant;
    }

    public IssuedToken reissue(UUID userId, UUID workspaceId) {
        MembershipRecord membership = tenant.run(workspaceId, userId, () ->
                workspaces.findMembership(workspaceId, userId).orElse(null));
        if (membership == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "MEMBERSHIP_LOST", "You are no longer a member of this workspace.");
        }
        if (membership.status() != MembershipStatus.ACTIVE) {
            throw new ApiException(HttpStatus.FORBIDDEN, "MEMBERSHIP_SUSPENDED", "Your membership is suspended.");
        }
        return tokens.issue(userId, workspaceId, membership.role().name(), membership.departmentId());
    }
}
