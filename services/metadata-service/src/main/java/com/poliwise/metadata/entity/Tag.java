package com.poliwise.metadata.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "tags", schema = "metadata")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Tag {
    @Id
    @Column(columnDefinition = "uuid")
    private UUID id;

    @Column(nullable = false, unique = true)
    private String name;

    @Column(nullable = false, unique = true)
    private String slug;

    @Column
    private String color;

    @Column(name = "usage_count")
    private Integer usageCount;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;
}
