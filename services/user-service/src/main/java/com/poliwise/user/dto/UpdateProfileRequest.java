package com.poliwise.user.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;

public record UpdateProfileRequest(
        @NotBlank(message = "Full name is required")
        @Size(max = 200, message = "Full name must not exceed 200 characters")
        String fullName,

        @Pattern(regexp = "^\\+?[0-9]{7,15}$", message = "Invalid phone number format")
        String phone,

        @Size(max = 200, message = "Position must not exceed 200 characters")
        String position,

        @Size(max = 500, message = "Avatar URL must not exceed 500 characters")
        String avatarUrl,

        @Size(max = 1000, message = "Bio must not exceed 1000 characters")
        String bio,

        LocalDate dateOfBirth
) {}
