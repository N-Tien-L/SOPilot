package com.poliwise.auth.dto.auth;

/**
 * Verified claims extracted from a valid Google ID token.
 */
public record GoogleTokenPayload(
        String email,
        String sub,
        String name,
        String picture,
        boolean emailVerified
) {}
