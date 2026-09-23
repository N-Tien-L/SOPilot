package com.poliwise.knowledge.dto.event;

import com.poliwise.knowledge.enums.ChunkingStrategy;
import com.poliwise.knowledge.enums.EmbeddingModel;
import com.poliwise.knowledge.enums.FileType;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.time.OffsetDateTime;
import java.util.UUID;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record DocumentUploadedEvent(
        UUID eventId,
        UUID documentId,
        String fileName,
        FileType fileType,
        Long fileSizeBytes,
        String fileKey,
        UUID uploadedBy,
        ChunkingStrategy chunkingStrategy,
        EmbeddingModel embeddingModel,
        OffsetDateTime occurredAt
) {

    public static DocumentUploadedEvent create(
            UUID documentId, String fileName, FileType fileType,
            Long fileSizeBytes, String fileKey, UUID uploadedBy,
            ChunkingStrategy chunkingStrategy, EmbeddingModel embeddingModel) {
        return new DocumentUploadedEvent(
                UUID.randomUUID(),
                documentId, fileName, fileType,
                fileSizeBytes, fileKey, uploadedBy,
                chunkingStrategy, embeddingModel,
                OffsetDateTime.now()
        );
    }
}