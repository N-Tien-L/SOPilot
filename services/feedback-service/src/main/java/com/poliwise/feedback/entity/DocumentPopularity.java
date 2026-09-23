package com.poliwise.feedback.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "document_popularity", schema = "analytics")
public class DocumentPopularity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "document_id", nullable = false, unique = true)
    private UUID documentId;

    @Column(name = "total_citations")
    private Integer totalCitations = 0;

    @Column(name = "unique_questions_cited")
    private Integer uniqueQuestionsCited = 0;

    @Column(name = "citations_with_likes")
    private Integer citationsWithLikes = 0;

    @Column(name = "citations_with_dislikes")
    private Integer citationsWithDislikes = 0;

    @Column(name = "first_cited_at")
    private Instant firstCitedAt;

    @Column(name = "last_cited_at")
    private Instant lastCitedAt;

    @Column(name = "citations_last_7_days")
    private Integer citationsLast7Days = 0;

    @Column(name = "citations_last_30_days")
    private Integer citationsLast30Days = 0;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at")
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
        updatedAt = Instant.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }
}
