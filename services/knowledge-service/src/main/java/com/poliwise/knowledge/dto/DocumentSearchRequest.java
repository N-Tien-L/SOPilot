package com.poliwise.knowledge.dto;

import com.poliwise.knowledge.enums.FileType;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.util.List;
import java.util.UUID;

public record DocumentSearchRequest(
        Integer page,
        Integer size,
        String search,
        FileType fileType,
        UUID uploadedBy,
        java.time.LocalDate startDate,
        java.time.LocalDate endDate,
        String status,
        UUID categoryId,
        List<String> tags,
        String sortBy,
        String sortOrder
) {
    public DocumentSearchRequest {
        if (page == null || page < 1) page = 1;
        if (size == null || size < 1) size = 20;
        if (size > 100) size = 100;
        if (sortOrder == null) sortOrder = "desc";
    }
}
