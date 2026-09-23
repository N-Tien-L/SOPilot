package com.poliwise.auth.dto.auth;

import java.time.Instant;
import java.util.UUID;

public record LoginHistoryInfo(
        UUID id,
        String username,
        String ipAddress,
        String deviceType,
        String location,
        String status,
        String failureReason,
        Instant createdAt
) {}
