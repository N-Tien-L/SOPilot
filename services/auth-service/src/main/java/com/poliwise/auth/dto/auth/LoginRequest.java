package com.poliwise.auth.dto.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record LoginRequest(
        String username,
        @NotBlank @Size(min = 8, max = 128) String password) {
}
