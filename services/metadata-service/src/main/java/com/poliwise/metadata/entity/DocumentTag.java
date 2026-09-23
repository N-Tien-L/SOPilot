package com.poliwise.metadata.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "document_tags", schema = "metadata")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocumentTag {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "document_metadata_id", nullable = false)
    private UUID documentMetadataId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "tag_id", nullable = false)
    private Tag tag;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;
}
