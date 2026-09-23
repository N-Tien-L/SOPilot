package com.poliwise.metadata.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.UUID;

public record CreateTagRequest(
        @NotBlank(message = "name is required") @Size(max = 50, message = "name must be at most 50 characters") String name,
        @Size(max = 7, message = "color must be a valid hex color") String color
) {}