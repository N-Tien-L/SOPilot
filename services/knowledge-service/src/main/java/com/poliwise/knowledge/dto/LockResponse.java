package com.poliwise.knowledge.dto;

import java.util.UUID;

public record LockResponse(
    UUID documentId,
    UUID lockedBy,
    String lockedByUsername,
    int versionAtLock,
    String lockToken,
    java.time.OffsetDateTime lockedAt,
    java.time.OffsetDateTime expiresAt
) {}
