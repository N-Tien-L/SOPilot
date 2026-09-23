package com.poliwise.auth.dto.auth;

public record TokenResponse(String accessToken, String refreshToken, String tokenType,
        long expiresInSeconds, AuthUserView user) {
}
