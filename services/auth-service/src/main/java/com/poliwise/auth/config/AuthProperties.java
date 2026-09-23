package com.poliwise.auth.config;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "auth")
public record AuthProperties(@NotNull Jwt jwt, @NotNull RefreshToken refreshToken,
        @NotNull Login login) {

    public record Jwt(@NotBlank String secret, @NotBlank String issuer,
            @NotNull Duration accessTokenTtl) {
    }

    public record RefreshToken(@NotNull Duration ttl) {
    }

    public record Login(@Min(1) int maxFailedAttempts, @NotNull Duration lockDuration) {
    }
}
