package com.poliwise.auth.dto.auth;

public record ClientMetadata(String ipAddress, String userAgent, String deviceInfo) {

    public static ClientMetadata empty() {
        return new ClientMetadata(null, null, null);
    }
}
