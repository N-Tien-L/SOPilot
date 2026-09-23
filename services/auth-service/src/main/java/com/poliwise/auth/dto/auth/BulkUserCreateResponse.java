package com.poliwise.auth.dto.auth;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record BulkUserCreateResponse(
        int totalRequested,
        int successCount,
        int failureCount,
        List<CreatedUserInfo> successfulUsers,
        List<FailedUserInfo> failedUsers
) {
    public record CreatedUserInfo(
            UUID userId,
            String username,
            String email,
            String tempPassword,
            boolean emailSent
    ) {}

    public record FailedUserInfo(
            String username,
            String email,
            String error
    ) {}
}
