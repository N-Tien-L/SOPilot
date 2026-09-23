package com.poliwise.metadata.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.UUID;

public record CreateCategoryRequest(
        @NotBlank(message = "name is required") @Size(max = 100, message = "name must be at most 100 characters") String name,
        @Size(max = 500, message = "description must be at most 500 characters") String description,
        UUID parentId,
        @Size(max = 50, message = "icon must be at most 50 characters") String icon,
        Integer displayOrder
) {}