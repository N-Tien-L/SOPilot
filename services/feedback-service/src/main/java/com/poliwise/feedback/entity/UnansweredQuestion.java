package com.poliwise.feedback.entity;

import com.poliwise.feedback.enums.PriorityLevel;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import com.poliwise.feedback.enums.UnansweredStatus;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "unanswered_questions", schema = "conversation")
public class UnansweredQuestion {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "message_id")
    private UUID messageId;

    @Column(name = "conversation_id")
    private UUID conversationId;

    @Column(name = "question", nullable = false, columnDefinition = "TEXT")
    private String question;

    @Column(name = "question_normalized", columnDefinition = "TEXT")
    private String questionNormalized;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "attempted_context", columnDefinition = "jsonb")
    private String attemptedContext;

    @Column(name = "search_query", columnDefinition = "TEXT")
    private String searchQuery;

    @Column(name = "top_similarity_score", precision = 5, scale = 4)
    private BigDecimal topSimilarityScore;

    @Column(name = "user_department_id")
    private UUID userDepartmentId;

    @Column(name = "user_role", length = 20)
    private String userRole;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", length = 20, nullable = false)
    private UnansweredStatus status = UnansweredStatus.PENDING;

    @Column(name = "resolved")
    private Boolean resolved = false;

    @Column(name = "resolved_by")
    private UUID resolvedBy;

    @Column(name = "resolved_at")
    private Instant resolvedAt;

    @Column(name = "resolution_notes", columnDefinition = "TEXT")
    private String resolutionNotes;

    @Column(name = "related_document_id")
    private UUID relatedDocumentId;

    @Column(name = "category", length = 100)
    private String category;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "priority", nullable = false)
    private PriorityLevel priority = PriorityLevel.NORMAL;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at")
    private Instant updatedAt;

    @Column(name = "deleted_at")
    private Instant deletedAt;

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
