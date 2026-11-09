package com.sopilot.core.identity;

import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.identity.dto.DevLoginRequest;
import com.sopilot.core.identity.dto.LoginResponse;
import jakarta.validation.Valid;
import org.springframework.context.annotation.Profile;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Locale;

/**
 * Login without Google for tests and eval (TECH §5.1). The bean only exists in the
 * {@code local} and {@code test} profiles; in any other profile the route is not registered
 * and returns {@code 404}. Uses issuer {@code sopilot-dev}, subject = email, and the same JIT
 * flow as Google.
 */
@RestController
@Profile({"local", "test"})
@RequestMapping(AuthCookies.AUTH_PATH)
public class DevLoginController {

    public static final String DEV_ISSUER = "sopilot-dev";

    private final IdentityService identityService;
    private final AuthCookies cookies;
    private final RefreshTokenService refreshTokens;

    public DevLoginController(IdentityService identityService, AuthCookies cookies,
                              RefreshTokenService refreshTokens) {
        this.identityService = identityService;
        this.cookies = cookies;
        this.refreshTokens = refreshTokens;
    }

    @PostMapping("/dev-login")
    public ResponseEntity<ApiResponse<LoginResponse>> devLogin(@Valid @RequestBody DevLoginRequest request) {
        String email = request.email().trim().toLowerCase(Locale.ROOT);
        String name = request.displayName() != null && !request.displayName().isBlank()
                ? request.displayName().trim()
                : email.split("@")[0];
        IdentityService.LoginSession session = identityService.loginWithSession(
                new ExternalIdentityClaims(DEV_ISSUER, email, email, name, null, null));
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .header(HttpHeaders.SET_COOKIE, cookies.refreshCookie(session.refreshToken(), refreshTokens.ttl()))
                .body(ApiResponse.of(session.response()));
    }
}
