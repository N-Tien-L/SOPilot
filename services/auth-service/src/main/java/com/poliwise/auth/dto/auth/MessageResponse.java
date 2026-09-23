package com.poliwise.auth.dto.auth;

import jakarta.validation.constraints.NotBlank;

public record MessageResponse(
        boolean success,
        String message
) {
    public static MessageResponse ok(String message) {
        return new MessageResponse(true, message);
    }

    public static MessageResponse error(String message) {
        return new MessageResponse(false, message);
    }
}
