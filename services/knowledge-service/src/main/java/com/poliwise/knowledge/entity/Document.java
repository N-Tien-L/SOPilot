package com.poliwise.knowledge.entity;

import com.poliwise.knowledge.enums.ChunkingStrategy;
import com.poliwise.knowledge.enums.EmbeddingModel;
import com.poliwise.knowledge.enums.FileType;
import com.poliwise.knowledge.enums.ProcessingStatus;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "documents", schema = "knowledge")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Document {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "original_filename")
    private String originalFilename;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "file_type", columnDefinition = "knowledge.file_type")
    private FileType fileType;

    @Column(name = "file_size_bytes")
    private Long fileSizeBytes;

    @Column(name = "mime_type")
    private String mimeType;

    @Column(name = "file_key")
    private String fileKey;

    @Column(name = "bucket_name")
    private String bucketName;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "status", columnDefinition = "knowledge.processing_status")
    private ProcessingStatus status;

    @Column(name = "current_version")
    private Integer currentVersion;

    @Column(name = "extracted_text", columnDefinition = "text")
    private String extractedText;

    @Column(name = "page_count")
    private Integer pageCount;

    @Column(name = "word_count")
    private Integer wordCount;

    @Column(name = "language")
    private String language;

    @Column(name = "ocr_required")
    private Boolean ocrRequired;

    @Column(name = "ocr_confidence")
    private BigDecimal ocrConfidence;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "chunking_strategy", columnDefinition = "knowledge.chunking_strategy")
    private ChunkingStrategy chunkingStrategy;

    @Column(name = "chunk_size")
    private Integer chunkSize;

    @Column(name = "chunk_overlap")
    private Integer chunkOverlap;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "embedding_model", columnDefinition = "knowledge.embedding_model")
    private EmbeddingModel embeddingModel;

    @Column(name = "uploaded_by")
    private UUID uploadedBy;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    @Column(name = "deleted_at")
    private OffsetDateTime deletedAt;

    @Column(name = "expires_at")
    private OffsetDateTime expiresAt;

    /* ===== Helper methods cho pipeline ===== */

    public boolean isReady() {
        return status == ProcessingStatus.READY;
    }

    public boolean isProcessing() {
        return status == ProcessingStatus.PARSING || status == ProcessingStatus.CHUNKING
                || status == ProcessingStatus.EMBEDDING || status == ProcessingStatus.INDEXING;
    }
}
