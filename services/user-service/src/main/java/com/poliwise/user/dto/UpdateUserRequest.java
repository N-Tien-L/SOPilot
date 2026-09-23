package com.poliwise.user.dto;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;

import java.util.UUID;

public record UpdateUserRequest(
        UserRole role,
        AccountStatus status,
        UUID departmentId
) {}
