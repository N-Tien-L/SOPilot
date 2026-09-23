package com.poliwise.auth.dto.auth;

import com.poliwise.auth.enums.UserRole;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RegisterRequest(@NotBlank @Size(min = 3, max = 100) String username,
        @NotBlank @Email @Size(max = 255) String email,
        @NotBlank @Size(min = 8, max = 128) String password, UserRole role) {
}
