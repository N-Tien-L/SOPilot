package com.poliwise.knowledge.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "document_version_deletions", schema = "knowledge")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocumentVersionDeletion {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "document_id", nullable = false)
    private UUID documentId;

    @Column(name = "version_number", nullable = false)
    private Integer versionNumber;

    @Column(name = "deleted_by", nullable = false)
    private UUID deletedBy;

    @Column(name = "deleted_at", nullable = false)
    private OffsetDateTime deletedAt;

    @Column(name = "file_key")
    private String fileKey;

    @Column(name = "file_size_bytes")
    private Long fileSizeBytes;

    @Column(name = "changelog", columnDefinition = "text")
    private String changelog;

    @Column(name = "extracted_text", columnDefinition = "text")
    private String extractedText;
}
