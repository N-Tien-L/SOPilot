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
@Table(name = "hourly_aggregates", schema = "analytics",
       uniqueConstraints = @UniqueConstraint(columnNames = {"datetime"}))
public class HourlyAggregate {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "datetime", nullable = false)
    private Instant datetime;

    @Column(name = "hour")
    private Integer hour;

    @Column(name = "total_questions")
    private Integer totalQuestions = 0;

    @Column(name = "total_requests")
    private Integer totalRequests = 0;

    @Column(name = "total_errors")
    private Integer totalErrors = 0;

    @Column(name = "unique_users")
    private Integer uniqueUsers = 0;

    @Column(name = "avg_response_time_ms")
    private Integer avgResponseTimeMs;

    @Column(name = "likes")
    private Integer likes = 0;

    @Column(name = "dislikes")
    private Integer dislikes = 0;

    @Column(name = "computed_at")
    private Instant computedAt;
}
