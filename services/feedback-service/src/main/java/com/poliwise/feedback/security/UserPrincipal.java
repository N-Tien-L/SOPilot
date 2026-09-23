package com.poliwise.feedback.security;

import lombok.Builder;
import lombok.Getter;

import java.util.UUID;

@Getter
@Builder
public class UserPrincipal {
    private final UUID userId;
    private final String username;
    private final String email;
    private final String role;
    private final String status;
    private final UUID departmentId;
}
