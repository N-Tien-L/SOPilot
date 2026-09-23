package com.poliwise.auth.dto.auth;

public record ChangePasswordResponse(
        boolean success,
        String message
) {
    public static ChangePasswordResponse ok(String message) {
        return new ChangePasswordResponse(true, message);
    }

    public static ChangePasswordResponse error(String message) {
        return new ChangePasswordResponse(false, message);
    }
}
