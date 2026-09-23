package com.poliwise.feedback.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "daily_aggregates", schema = "analytics")
public class DailyAggregate {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "date", nullable = false, unique = true)
    private LocalDate date;

    @Column(name = "total_questions")
    private Integer totalQuestions = 0;

    @Column(name = "total_conversations")
    private Integer totalConversations = 0;

    @Column(name = "unique_users_asked")
    private Integer uniqueUsersAsked = 0;

    @Column(name = "total_likes")
    private Integer totalLikes = 0;

    @Column(name = "total_dislikes")
    private Integer totalDislikes = 0;

    @Column(name = "feedback_ratio", precision = 5, scale = 4)
    private BigDecimal feedbackRatio;

    @Column(name = "avg_response_time_ms")
    private Integer avgResponseTimeMs;

    @Column(name = "p50_response_time_ms")
    private Integer p50ResponseTimeMs;

    @Column(name = "p95_response_time_ms")
    private Integer p95ResponseTimeMs;

    @Column(name = "p99_response_time_ms")
    private Integer p99ResponseTimeMs;

    @Column(name = "total_requests")
    private Integer totalRequests = 0;

    @Column(name = "total_errors")
    private Integer totalErrors = 0;

    @Column(name = "error_rate", precision = 5, scale = 4)
    private BigDecimal errorRate;

    @Column(name = "total_tokens_used")
    private Long totalTokensUsed = 0L;

    @Column(name = "avg_tokens_per_question")
    private Integer avgTokensPerQuestion;

    @Column(name = "avg_chunks_retrieved", precision = 5, scale = 2)
    private BigDecimal avgChunksRetrieved;

    @Column(name = "documents_uploaded")
    private Integer documentsUploaded = 0;

    @Column(name = "documents_published")
    private Integer documentsPublished = 0;

    @Column(name = "unique_active_users")
    private Integer uniqueActiveUsers = 0;

    @Column(name = "new_users")
    private Integer newUsers = 0;

    @Column(name = "unanswered_questions")
    private Integer unansweredQuestions = 0;

    @Column(name = "resolved_questions")
    private Integer resolvedQuestions = 0;

    @Column(name = "computed_at")
    private Instant computedAt;

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
