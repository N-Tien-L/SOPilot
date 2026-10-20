package com.poliwise.auth.dto.roster;

import java.util.UUID;

public record AdmitGoogleLoginRequest(String email, UUID userId) {}
