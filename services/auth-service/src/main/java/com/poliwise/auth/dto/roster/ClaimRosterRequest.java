package com.poliwise.auth.dto.roster;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

/**
 * Request payload sent from auth-service to user-service
 * for atomic JIT claiming of pre-provisioned employee roster.
 */
public record ClaimRosterRequest(
        @NotBlank(message = "Email is required")
        @Email(message = "Invalid email format")
        String email,

        String googleSub
) {}
