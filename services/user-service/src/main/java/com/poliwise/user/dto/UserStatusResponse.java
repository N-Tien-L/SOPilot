package com.poliwise.user.dto;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.UUID;

public record UserStatusResponse(
        UUID userId,
        AccountStatus status,
        UserRole role,
        boolean isActive,
        OffsetDateTime deletedAt
) {}
