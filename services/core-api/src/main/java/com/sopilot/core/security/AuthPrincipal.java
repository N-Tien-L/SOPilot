package com.sopilot.core.security;

import com.sopilot.core.common.ApiException;
import org.springframework.http.HttpStatus;

import java.util.UUID;

/**
 * Identity of the caller, taken only from a verified access token (TECH §4.3): never from a body,
 * path or query. {@code role} and {@code departmentId} can be up to one access-token lifetime stale.
 */
public record AuthPrincipal(UUID userId, UUID workspaceId, WorkspaceRole role, UUID departmentId) {

    public boolean isManager() {
        return role == WorkspaceRole.OWNER || role == WorkspaceRole.ADMIN;
    }

    public void requireManager() {
        if (!isManager()) {
            throw forbidden();
        }
    }

    public void requireOwner() {
        if (role != WorkspaceRole.OWNER) {
            throw forbidden();
        }
    }

    private static ApiException forbidden() {
        return new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "You do not have permission to do this.");
    }
}
