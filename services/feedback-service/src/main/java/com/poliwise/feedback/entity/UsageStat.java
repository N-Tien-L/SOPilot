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
@Table(name = "usage_stats", schema = "analytics")
public class UsageStat {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "user_id")
    private UUID userId;

    @Column(name = "user_role", length = 20)
    private String userRole;

    @Column(name = "user_department_id")
    private UUID userDepartmentId;

    @Column(name = "service_name", nullable = false, length = 50)
    private String serviceName;

    @Column(name = "endpoint", nullable = false, length = 255)
    private String endpoint;

    @Column(name = "method", nullable = false, length = 10)
    private String method;

    @Column(name = "response_time_ms", nullable = false)
    private Integer responseTimeMs;

    @Column(name = "status_code", nullable = false)
    private Integer statusCode;

    @Column(name = "request_size_bytes")
    private Integer requestSizeBytes;

    @Column(name = "response_size_bytes")
    private Integer responseSizeBytes;

    @Column(name = "is_error")
    private Boolean isError = false;

    @Column(name = "error_code", length = 50)
    private String errorCode;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "tokens_used")
    private Integer tokensUsed;

    @Column(name = "model_used", length = 50)
    private String modelUsed;

    @Column(name = "chunks_retrieved")
    private Integer chunksRetrieved;

    @Column(name = "confidence", length = 20)
    private String confidence;

    @Column(name = "trace_id", length = 100)
    private String traceId;

    @JdbcTypeCode(SqlTypes.INET)
    @Column(name = "ip_address")
    private String ipAddress;

    @Column(name = "user_agent", columnDefinition = "TEXT")
    private String userAgent;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
