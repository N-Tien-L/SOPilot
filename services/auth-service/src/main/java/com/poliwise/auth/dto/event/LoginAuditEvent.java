package com.poliwise.auth.dto.event;

import java.time.OffsetDateTime;
import java.util.UUID;

public record LoginAuditEvent(
        UUID eventId,
        UUID userId,
        String username,
        String status,
        String failureReason,
        String ipAddress,
        String userAgent,
        OffsetDateTime occurredAt
) {

    public static LoginAuditEvent success(UUID userId, String username, String ipAddress, String userAgent) {
        return new LoginAuditEvent(UUID.randomUUID(), userId, username, "SUCCESS", null, ipAddress, userAgent, OffsetDateTime.now());
    }

    public static LoginAuditEvent failed(UUID userId, String username, String reason, String ipAddress, String userAgent) {
        return new LoginAuditEvent(UUID.randomUUID(), userId, username, "FAILED", reason, ipAddress, userAgent, OffsetDateTime.now());
    }

    public static LoginAuditEvent logout(UUID userId, String username, String ipAddress, String userAgent) {
        return new LoginAuditEvent(UUID.randomUUID(), userId, username, "LOGOUT", null, ipAddress, userAgent, OffsetDateTime.now());
    }
}
