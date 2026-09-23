package com.poliwise.user.dto;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;

import java.util.UUID;

public record UserSearchCriteria(
        String keyword,
        UserRole role,
        AccountStatus status,
        UUID departmentId,
        Boolean includeDeleted
) {}
