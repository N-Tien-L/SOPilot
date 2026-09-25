package com.poliwise.user.dto.roster;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public record ClaimRosterRequest(
        @NotBlank(message = "Email is required")
        @Email(message = "Invalid email format")
        String email,

        String googleSub
) {}
