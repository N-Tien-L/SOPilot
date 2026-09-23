package com.poliwise.metadata.dto.event;

import com.poliwise.metadata.enums.ChunkingStrategy;
import com.poliwise.metadata.enums.EmbeddingModel;

import java.time.OffsetDateTime;
import java.util.UUID;

public record DocumentUploadedEvent(
        UUID eventId,
        UUID documentId,
        String fileName,
        String fileType,
        Long fileSizeBytes,
        String fileKey,
        UUID uploadedBy,
        ChunkingStrategy chunkingStrategy,
        EmbeddingModel embeddingModel,
        OffsetDateTime occurredAt
) {

    public static DocumentUploadedEvent create(
            UUID documentId, String fileName, String fileType,
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