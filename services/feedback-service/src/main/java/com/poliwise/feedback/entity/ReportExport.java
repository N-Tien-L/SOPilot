package com.poliwise.feedback.entity;

import com.poliwise.feedback.enums.ExportFormat;
import com.poliwise.feedback.enums.ExportStatus;
import com.poliwise.feedback.enums.ReportType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcType;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.dialect.PostgreSQLEnumJdbcType;
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
@Table(name = "report_exports", schema = "analytics")
public class ReportExport {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", nullable = false)
    private UUID id;

    @Enumerated(EnumType.STRING)
    @JdbcType(PostgreSQLEnumJdbcType.class)
    @Column(name = "report_type", nullable = false, columnDefinition = "analytics.report_type")
    private ReportType reportType;

    @Column(name = "title", nullable = false, length = 255)
    private String title;

    @Column(name = "date_from")
    private LocalDate dateFrom;

    @Column(name = "date_to")
    private LocalDate dateTo;

    @Column(name = "department_id")
    private UUID departmentId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "filters", columnDefinition = "jsonb")
    private String filters;

    @Enumerated(EnumType.STRING)
    @JdbcType(PostgreSQLEnumJdbcType.class)
    @Column(name = "format", nullable = false, columnDefinition = "analytics.export_format")
    private ExportFormat format;

    @Column(name = "file_key", length = 500)
    private String fileKey;

    @Column(name = "file_size_bytes")
    private Integer fileSizeBytes;

    @Enumerated(EnumType.STRING)
    @JdbcType(PostgreSQLEnumJdbcType.class)
    @Column(name = "status", nullable = false, columnDefinition = "analytics.report_status")
    private ExportStatus status = ExportStatus.PENDING;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "requested_by", nullable = false)
    private UUID requestedBy;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @Column(name = "downloaded_at")
    private Instant downloadedAt;

    @Column(name = "expires_at")
    private Instant expiresAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
