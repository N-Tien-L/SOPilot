package com.sopilot.core.identity;

import com.sopilot.core.common.ApiErrorResponse;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.config.SopilotProperties;
import com.sopilot.core.identity.RefreshTokenService.Rotation;
import com.sopilot.core.identity.dto.GoogleLoginRequest;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.identity.dto.NonceResponse;
import com.sopilot.core.identity.dto.SwitchWorkspaceRequest;
import com.sopilot.core.security.AccessTokenVerifier;
import com.sopilot.core.security.AuthPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Google login (FR-01, A9), refresh-token rotation, logout and workspace switching
 * (TECH-V2-core-api §5.1). The refresh token travels only in the {@code sp_refresh} cookie.
 */
@RestController
@RequestMapping(AuthCookies.AUTH_PATH)
public class AuthController {

    private static final String BEARER = "Bearer ";

    private final NonceService nonces;
    private final GoogleIdTokenVerifier verifier;
    private final IdentityService identityService;
    private final AuthCookies cookies;
    private final RefreshTokenService refreshTokens;
    private final WorkspaceSessionService workspaceSessions;
    private final AccessTokenVerifier accessTokens;
    private final String frontendOrigin;

    public AuthController(NonceService nonces, GoogleIdTokenVerifier verifier, IdentityService identityService,
                          AuthCookies cookies, RefreshTokenService refreshTokens, WorkspaceSessionService workspaceSessions,
                          AccessTokenVerifier accessTokens, SopilotProperties properties) {
        this.nonces = nonces;
        this.verifier = verifier;
        this.identityService = identityService;
        this.cookies = cookies;
        this.refreshTokens = refreshTokens;
        this.workspaceSessions = workspaceSessions;
        this.accessTokens = accessTokens;
        this.frontendOrigin = properties.auth().frontendOrigin();
    }

    @PostMapping("/google/nonce")
    public ResponseEntity<ApiResponse<NonceResponse>> nonce() {
        NonceService.IssuedNonce issued = nonces.issue();
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.SET_COOKIE, cookies.nonceCookie(issued.cookieValue(), nonces.ttl()))
                .body(ApiResponse.of(new NonceResponse(issued.nonce())));
    }

    @PostMapping("/google")
    public ResponseEntity<ApiResponse<LoginResponse>> google(
            @Valid @RequestBody GoogleLoginRequest request,
            @CookieValue(name = AuthCookies.NONCE_COOKIE, required = false) String nonceCookie,
            HttpServletResponse response) {
        // Single use from the browser's side: cleared on every outcome, including errors.
        response.addHeader(HttpHeaders.SET_COOKIE, cookies.clearNonceCookie());
        String expectedNonce = nonces.validate(nonceCookie).orElse(null);
        ExternalIdentityClaims identity = verifier.verify(request.idToken(), expectedNonce);
        IdentityService.LoginSession session = identityService.loginWithSession(identity);
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.SET_COOKIE, cookies.refreshCookie(session.refreshToken(), refreshTokens.ttl()))
                .body(ApiResponse.of(session.response()));
    }

    /** Exchanges the refresh cookie for a new access token and the next refresh token (rotation). */
    @PostMapping("/refresh")
    public ResponseEntity<?> refresh(
            @CookieValue(name = AuthCookies.REFRESH_COOKIE, required = false) String refreshCookie,
            HttpServletRequest request) {
        requireFrontendOrigin(request);
        if (refreshCookie == null || refreshCookie.isBlank()) {
            throw unauthenticated();
        }
        Rotation rotation = refreshTokens.rotate(refreshCookie);
        if (!rotation.accepted()) {
            return ResponseEntity.status(rotation.status())
                    .cacheControl(CacheControl.noStore())
                    .header(HttpHeaders.SET_COOKIE, cookies.clearRefreshCookie())
                    .body(ApiErrorResponse.of(rotation.code(), rotation.message(), Map.of()));
        }
        LoginResponse login = identityService.describe(rotation.userId(), rotation.workspaceId(), rotation.access());
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.SET_COOKIE, cookies.refreshCookie(rotation.refreshToken(), refreshTokens.ttl()))
                .body(ApiResponse.of(login));
    }

    /** Ends the current refresh chain. Always {@code 204}: whether the cookie was valid is not revealed. */
    @PostMapping("/logout")
    public ResponseEntity<Void> logout(
            @CookieValue(name = AuthCookies.REFRESH_COOKIE, required = false) String refreshCookie,
            HttpServletRequest request) {
        requireFrontendOrigin(request);
        if (refreshCookie != null && !refreshCookie.isBlank()) {
            refreshTokens.revokeChain(refreshCookie, "LOGOUT");
        }
        return ResponseEntity.noContent()
                .header(HttpHeaders.SET_COOKIE, cookies.clearRefreshCookie())
                .build();
    }

    /** Needs a bearer token; this path is outside the bearer filter because login and refresh have none. */
    @PostMapping("/switch-workspace")
    public ResponseEntity<ApiResponse<LoginResponse>> switchWorkspace(
            @Valid @RequestBody SwitchWorkspaceRequest body,
            @CookieValue(name = AuthCookies.REFRESH_COOKIE, required = false) String refreshCookie,
            HttpServletRequest request) {
        AuthPrincipal caller = bearerPrincipal(request);
        IdentityService.LoginSession session =
                workspaceSessions.switchTo(caller.userId(), body.workspaceId(), refreshCookie);
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.SET_COOKIE, cookies.refreshCookie(session.refreshToken(), refreshTokens.ttl()))
                .body(ApiResponse.of(session.response()));
    }

    private AuthPrincipal bearerPrincipal(HttpServletRequest request) {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith(BEARER)) {
            throw unauthenticated();
        }
        return accessTokens.verify(header.substring(BEARER.length()).trim()).orElseThrow(AuthController::unauthenticated);
    }

    private static ApiException unauthenticated() {
        return new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHENTICATED", "Sign in to continue.");
    }

    /** Second CSRF layer next to SameSite=Strict (TECH §5.1): cookie-authenticated calls need the frontend Origin. */
    private void requireFrontendOrigin(HttpServletRequest request) {
        if (!frontendOrigin.equals(request.getHeader(HttpHeaders.ORIGIN))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "You do not have permission to do this.");
        }
    }

    @ExceptionHandler(GoogleTokenRejectedException.class)
    public ResponseEntity<ApiErrorResponse> rejected(GoogleTokenRejectedException e) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(ApiErrorResponse.of("INVALID_GOOGLE_TOKEN", "Google sign-in could not be verified.", Map.of()));
    }
}
