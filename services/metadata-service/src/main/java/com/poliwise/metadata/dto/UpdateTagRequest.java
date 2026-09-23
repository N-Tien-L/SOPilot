package com.poliwise.metadata.dto;

import jakarta.validation.constraints.Size;

import java.util.UUID;

public record UpdateTagRequest(
        @Size(max = 50, message = "name must be at most 50 characters") String name,
        @Size(max = 7, message = "color must be a valid hex color") String color
) {}