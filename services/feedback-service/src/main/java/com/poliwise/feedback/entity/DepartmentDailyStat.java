package com.poliwise.feedback.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "department_daily_stats", schema = "analytics",
       uniqueConstraints = @UniqueConstraint(columnNames = {"date", "department_id"}))
public class DepartmentDailyStat {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "date", nullable = false)
    private LocalDate date;

    @Column(name = "department_id", nullable = false)
    private UUID departmentId;

    @Column(name = "total_questions")
    private Integer totalQuestions = 0;

    @Column(name = "unique_users")
    private Integer uniqueUsers = 0;

    @Column(name = "likes")
    private Integer likes = 0;

    @Column(name = "dislikes")
    private Integer dislikes = 0;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "top_categories", columnDefinition = "jsonb")
    private String topCategories;

    @Column(name = "computed_at")
    private Instant computedAt;
}
