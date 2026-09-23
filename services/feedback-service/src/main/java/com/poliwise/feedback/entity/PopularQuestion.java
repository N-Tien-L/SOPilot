package com.poliwise.feedback.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "popular_questions", schema = "analytics")
public class PopularQuestion {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "question_normalized", nullable = false, columnDefinition = "TEXT")
    private String questionNormalized;

    @Column(name = "question_sample", nullable = false, columnDefinition = "TEXT")
    private String questionSample;

    @Column(name = "ask_count")
    private Integer askCount = 1;

    @Column(name = "unique_users_count")
    private Integer uniqueUsersCount = 1;

    @Column(name = "first_asked_at", nullable = false)
    private Instant firstAskedAt;

    @Column(name = "last_asked_at", nullable = false)
    private Instant lastAskedAt;

    @Column(name = "total_likes")
    private Integer totalLikes = 0;

    @Column(name = "total_dislikes")
    private Integer totalDislikes = 0;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "common_source_documents", columnDefinition = "jsonb")
    private String commonSourceDocuments;

    @Column(name = "detected_category", length = 100)
    private String detectedCategory;

    @Column(name = "detected_department_id")
    private UUID detectedDepartmentId;

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
