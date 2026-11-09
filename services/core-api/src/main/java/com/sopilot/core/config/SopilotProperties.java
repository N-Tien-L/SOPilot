package com.sopilot.core.config;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.time.Duration;

/**
 * core-api settings (TECH-V2-core-api §9). Real values come from env; never log them.
 */
@Validated
@ConfigurationProperties(prefix = "sopilot")
public record SopilotProperties(@Valid @NotNull Google google,
                                @Valid @NotNull Jwt jwt,
                                @Valid @NotNull Auth auth) {

    /** Longest access-token lifetime allowed by the NFR (TECH §5.1). */
    public static final Duration MAX_ACCESS_TTL = Duration.ofMinutes(15);

    /**
     * @param clientId     OAuth client ID expected in {@code aud}; blank rejects every Google login
     * @param jwksUri      Google JWKS endpoint
     * @param jwksCacheTtl how long Google keys are cached before refresh
     */
    public record Google(String clientId, @NotNull String jwksUri, @NotNull Duration jwksCacheTtl) {
    }

    /**
     * @param privateKeyPath    PKCS#8 PEM RSA key used to sign access tokens
     * @param kid               key id published in JWKS; derived from the key thumbprint when blank
     * @param accessTtl         access-token lifetime, at most 15 minutes
     * @param generateIfMissing local/test only: create an in-memory key when no path is set
     * @param previousPublicKeyPath optional X.509 PEM public key of the key that was replaced; published in
     *                          JWKS and accepted for verification so rotating the signing key keeps sessions alive
     */
    public record Jwt(String privateKeyPath, String kid, @NotNull Duration accessTtl, boolean generateIfMissing,
                      String previousPublicKeyPath) {
    }

    /**
     * @param nonceHmacKey          HMAC key for the {@code sp_nonce} cookie, at least 32 bytes
     * @param nonceTtl              nonce lifetime
     * @param allowEphemeralNonceKey local/test only: generate a random key when none is set
     * @param cookieSecure          set the Secure attribute on auth cookies
     * @param refreshTtl            refresh-token lifetime (TECH §5.1, 14 days)
     * @param frontendOrigin        the only {@code Origin} accepted by refresh and logout (CSRF second layer)
     */
    public record Auth(String nonceHmacKey, @NotNull Duration nonceTtl, boolean allowEphemeralNonceKey,
                       boolean cookieSecure, @NotNull Duration refreshTtl, @NotNull String frontendOrigin) {
    }
}
