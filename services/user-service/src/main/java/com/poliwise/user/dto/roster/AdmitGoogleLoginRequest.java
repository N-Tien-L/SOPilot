package com.poliwise.user.dto.roster;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import java.util.UUID;

public record AdmitGoogleLoginRequest(@NotBlank @Email String email, UUID userId) {}
