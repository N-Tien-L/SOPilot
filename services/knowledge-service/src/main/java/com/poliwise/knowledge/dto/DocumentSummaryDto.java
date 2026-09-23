package com.poliwise.knowledge.dto;

public record DocumentSummaryDto(
        String id,
        String title,
        String fileName,
        long fileSize,
        String fileType,
        String status,
        int version,
        String uploadedAt,
        String updatedAt) {}
