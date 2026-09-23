package com.poliwise.auth.dto.auth;

public record ResetPasswordResponse(
        boolean success,
        String message
) {
    public static ResetPasswordResponse ok() {
        return new ResetPasswordResponse(true, "Password reset successfully.");
    }

    public static ResetPasswordResponse invalidToken() {
        return new ResetPasswordResponse(false, "Password reset token is invalid or expired.");
    }
}
