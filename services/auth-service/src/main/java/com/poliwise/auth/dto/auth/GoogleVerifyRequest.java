package com.poliwise.auth.dto.auth;

import jakarta.validation.constraints.NotBlank;

/**
 * Request payload for Google ID token verification endpoint.
 * POST /api/v1/auth/google/verify
 */
public record GoogleVerifyRequest(
        @NotBlank(message = "Google ID token is required")
        String idToken
) {}
