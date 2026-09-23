package com.poliwise.auth.config;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "email")
public record EmailProperties(
        String username,
        String appPassword,
        @NotBlank String fromName,
        @NotBlank @Email String fromAddress,
        @NotNull Boolean enabled
) {
}
