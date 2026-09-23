package com.poliwise.knowledge.dto;

import com.poliwise.knowledge.enums.ChunkingStrategy;
import com.poliwise.knowledge.enums.EmbeddingModel;
import com.poliwise.knowledge.enums.FileType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record UploadDocumentRequest(
        @NotBlank(message = "File name is required")
        String fileName,

        @NotNull(message = "File type is required")
        FileType fileType,

        @Positive(message = "File size must be positive")
        Long fileSizeBytes,

        String mimeType,

        ChunkingStrategy chunkingStrategy,

        Integer chunkSize,

        Integer chunkOverlap,

        EmbeddingModel embeddingModel,

        String language
) {}