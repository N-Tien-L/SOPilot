package com.sopilot.core.identity;

import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.security.AuthPrincipal;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code POST /api/v1/workspaces}: creates a TEAM workspace and returns tokens for it (TECH §5.2).
 * The other workspace routes are {@code workspace.WorkspaceController}.
 */
@RestController
@RequestMapping("/api/v1/workspaces")
public class WorkspaceSessionController {

    private final WorkspaceSessionService sessions;
    private final AuthCookies cookies;
    private final RefreshTokenService refreshTokens;

    public WorkspaceSessionController(WorkspaceSessionService sessions, AuthCookies cookies,
                                      RefreshTokenService refreshTokens) {
        this.sessions = sessions;
        this.cookies = cookies;
        this.refreshTokens = refreshTokens;
    }

    @PostMapping
    public ResponseEntity<ApiResponse<LoginResponse>> create(
            AuthPrincipal principal,
            @Valid @RequestBody CreateRequest request,
            @CookieValue(name = AuthCookies.REFRESH_COOKIE, required = false) String refreshCookie) {
        IdentityService.LoginSession session = sessions.createTeam(principal.userId(), request.name(), refreshCookie);
        return ResponseEntity.status(HttpStatus.CREATED)
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.SET_COOKIE, cookies.refreshCookie(session.refreshToken(), refreshTokens.ttl()))
                .body(ApiResponse.of(session.response()));
    }

    public record CreateRequest(@NotNull String name) {
    }
}
