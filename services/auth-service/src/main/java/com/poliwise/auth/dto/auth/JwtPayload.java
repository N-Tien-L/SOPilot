package com.poliwise.auth.dto.auth;

import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.UserRole;
import java.time.Instant;
import java.util.UUID;

public record JwtPayload(
        UUID sub,
        String username,
        String email,
        UserRole role,
        AccountStatus status,
        UUID department,
        Instant iat,
        Instant exp,
        String iss,
        String jti
) {}
