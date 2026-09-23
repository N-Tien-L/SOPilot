package com.poliwise.knowledge.dto;

import com.poliwise.knowledge.enums.ChunkingStrategy;
import com.poliwise.knowledge.enums.EmbeddingModel;
import com.poliwise.knowledge.enums.FileType;
import com.poliwise.knowledge.enums.ProcessingStatus;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DocumentResponse(
        UUID id,
        String originalFilename,
        FileType fileType,
        Long fileSizeBytes,
        String mimeType,
        ProcessingStatus status,
        Integer currentVersion,
        Integer pageCount,
        Integer wordCount,
        String language,
        Boolean ocrRequired,
        ChunkingStrategy chunkingStrategy,
        Integer chunkSize,
        Integer chunkOverlap,
        EmbeddingModel embeddingModel,
        UUID uploadedBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        // Metadata suggestion fields (Phase 1)
        String suggestedLanguage,
        String suggestedCategorySlug,
        String suggestedTitle,
        String suggestedDescription,
        java.util.List<String> suggestedTags,
        Boolean suggestedIsPolicy
) {}