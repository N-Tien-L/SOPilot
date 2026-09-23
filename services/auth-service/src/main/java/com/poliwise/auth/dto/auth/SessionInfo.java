package com.poliwise.auth.dto.auth;

import java.time.OffsetDateTime;
import java.util.UUID;

public record SessionInfo(
        UUID sessionId,
        String deviceInfo,
        String ipAddress,
        OffsetDateTime createdAt,
        OffsetDateTime expiresAt,
        boolean isCurrent
) {}
