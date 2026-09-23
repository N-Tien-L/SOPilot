package com.poliwise.user.dto;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;
import jakarta.validation.constraints.NotNull;

public record ChangeStatusRequest(
        @NotNull(message = "New status is required")
        AccountStatus newStatus,

        UserRole newRole
) {}
