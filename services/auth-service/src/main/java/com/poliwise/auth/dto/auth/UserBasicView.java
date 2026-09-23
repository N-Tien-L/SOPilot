package com.poliwise.auth.dto.auth;

import java.util.UUID;

public record UserBasicView(
        UUID id,
        String username,
        String email,
        String role,
        String status,
        UUID departmentId
) {}
