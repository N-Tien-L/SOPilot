package com.sopilot.core.identity.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * {@code POST /api/v1/auth/google}. {@code invitationToken} is accepted for contract stability
 * and applied from V2-30; it is ignored here.
 */
public record GoogleLoginRequest(@NotBlank @Size(max = 8192) String idToken,
                                 @Size(max = 256) String invitationToken) {

    @Override
    public String toString() {
        return "GoogleLoginRequest[<redacted>]";
    }
}
