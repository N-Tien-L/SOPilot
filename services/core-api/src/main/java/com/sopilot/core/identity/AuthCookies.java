package com.sopilot.core.identity;

import com.sopilot.core.config.SopilotProperties;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

import java.time.Duration;

/** Auth cookies: HttpOnly, SameSite=Strict, scoped to {@code /api/v1/auth} (TECH §5.1). */
@Component
public class AuthCookies {

    public static final String NONCE_COOKIE = "sp_nonce";
    public static final String AUTH_PATH = "/api/v1/auth";

    private final boolean secure;

    public AuthCookies(SopilotProperties properties) {
        this.secure = properties.auth().cookieSecure();
    }

    public String nonceCookie(String value, Duration maxAge) {
        return build(NONCE_COOKIE, value, maxAge);
    }

    public String clearNonceCookie() {
        return build(NONCE_COOKIE, "", Duration.ZERO);
    }

    private String build(String name, String value, Duration maxAge) {
        return ResponseCookie.from(name, value)
                .httpOnly(true)
                .secure(secure)
                .sameSite("Strict")
                .path(AUTH_PATH)
                .maxAge(maxAge)
                .build()
                .toString();
    }
}
