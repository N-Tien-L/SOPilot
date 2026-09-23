package com.poliwise.auth.dto.auth;

public record ForgotPasswordResponse(
        String message,
        boolean emailSent
) {
    private static final String GENERIC_MESSAGE =
            "If the email exists in the system, a password reset link will be sent.";

    public static ForgotPasswordResponse success() {
        return new ForgotPasswordResponse(GENERIC_MESSAGE, true);
    }

    public static ForgotPasswordResponse notFound() {
        return new ForgotPasswordResponse(GENERIC_MESSAGE, true);
    }
}
