package com.sopilot.core.identity.dto;

import java.util.List;
import java.util.UUID;

/**
 * Login result (TECH-V2-core-api §5.1). {@code pendingInvitations} stays empty until V2-30.
 */
public record LoginResponse(String accessToken,
                            long expiresIn,
                            UserView user,
                            WorkspaceView workspace,
                            List<PendingInvitationView> pendingInvitations) {

    public record UserView(UUID id, String email, String displayName) {
    }

    public record WorkspaceView(UUID id, String name, String kind, String role) {
    }

    public record PendingInvitationView(UUID id, String workspaceName, String role) {
    }

    @Override
    public String toString() {
        return "LoginResponse[accessToken=<redacted>, expiresIn=" + expiresIn + ", user=" + user.id()
                + ", workspace=" + workspace.id() + "]";
    }
}
