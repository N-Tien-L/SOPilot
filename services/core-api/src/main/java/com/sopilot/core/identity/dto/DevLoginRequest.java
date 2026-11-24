package com.sopilot.core.identity.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** {@code POST /api/v1/auth/dev-login}, local/test profiles only. */
public record DevLoginRequest(@NotBlank @Email @Size(max = 254) String email,
                              @Size(max = 100) String displayName) {
}
