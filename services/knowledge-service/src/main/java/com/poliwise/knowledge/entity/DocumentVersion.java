package com.poliwise.knowledge.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "document_versions", schema = "knowledge")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocumentVersion {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "document_id", nullable = false)
    private UUID documentId;

    @Column(name = "version_number")
    private Integer versionNumber;

    @Column(name = "file_key")
    private String fileKey;

    @Column(name = "file_size_bytes")
    private Long fileSizeBytes;

    @Column(name = "changelog", columnDefinition = "text")
    private String changelog;

    @Column(name = "extracted_text", columnDefinition = "text")
    private String extractedText;

    @Column(name = "created_by")
    private UUID createdBy;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    @Column(name = "deleted_at")
    private OffsetDateTime deletedAt;

    @Column(name = "deleted_by")
    private UUID deletedBy;

    @Column(name = "deletion_reason", columnDefinition = "text")
    private String deletionReason;

    @Column(name = "file_checksum")
    private String fileChecksum;
}
