package com.poliwise.feedback.entity;

import com.poliwise.feedback.enums.FeedbackType;
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
@Table(name = "feedbacks", schema = "analytics",
       uniqueConstraints = @UniqueConstraint(columnNames = {"user_id", "message_id"}))
public class Feedback {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "message_id", nullable = false)
    private UUID messageId;

    @Column(name = "conversation_id", nullable = false)
    private UUID conversationId;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "type", nullable = false)
    private FeedbackType type;

    @Column(name = "comment")
    private String comment;

    @Column(name = "question_text", columnDefinition = "TEXT")
    private String questionText;

    @Column(name = "answer_text", columnDefinition = "TEXT")
    private String answerText;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "sources_used", columnDefinition = "jsonb")
    private String sourcesUsed;

    @Column(name = "user_department_id")
    private UUID userDepartmentId;

    @Column(name = "user_role", length = 20)
    private String userRole;

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
