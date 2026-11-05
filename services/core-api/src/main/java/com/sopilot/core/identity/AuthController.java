package com.sopilot.core.identity;

import com.sopilot.core.common.ApiErrorResponse;
import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.identity.dto.GoogleLoginRequest;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.identity.dto.NonceResponse;
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
 * Google login (FR-01, A9; TECH-V2-core-api §5.1). Refresh, logout and workspace switching
 * are V2-29.
 */
@RestController
@RequestMapping(AuthCookies.AUTH_PATH)
public class AuthController {

    private final NonceService nonces;
    private final GoogleIdTokenVerifier verifier;
    private final IdentityService identityService;
    private final AuthCookies cookies;

    public AuthController(NonceService nonces, GoogleIdTokenVerifier verifier, IdentityService identityService,
                          AuthCookies cookies) {
        this.nonces = nonces;
        this.verifier = verifier;
        this.identityService = identityService;
        this.cookies = cookies;
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
        LoginResponse login = identityService.login(identity);
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .body(ApiResponse.of(login));
    }

    @ExceptionHandler(GoogleTokenRejectedException.class)
    public ResponseEntity<ApiErrorResponse> rejected(GoogleTokenRejectedException e) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(ApiErrorResponse.of("INVALID_GOOGLE_TOKEN", "Google sign-in could not be verified.", Map.of()));
    }
}
