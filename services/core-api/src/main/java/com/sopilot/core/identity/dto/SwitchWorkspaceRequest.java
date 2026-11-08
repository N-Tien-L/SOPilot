package com.sopilot.core.identity.dto;

import jakarta.validation.constraints.NotNull;

import java.util.UUID;

public record SwitchWorkspaceRequest(@NotNull UUID workspaceId) {
}
