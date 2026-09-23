package com.poliwise.knowledge.entity;

import com.poliwise.knowledge.enums.ProcessingStatus;
import com.poliwise.knowledge.enums.ProcessingStep;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "processing_jobs", schema = "knowledge")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ProcessingJob {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "document_id", nullable = false)
    private UUID documentId;

    @Column(name = "document_version_id")
    private UUID documentVersionId;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "job_type", columnDefinition = "knowledge.processing_step")
    private ProcessingStep jobType;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "status", columnDefinition = "knowledge.processing_status")
    private ProcessingStatus status;

    @Column(name = "progress_percent")
    private Integer progressPercent;

    @Column(name = "started_at")
    private OffsetDateTime startedAt;

    @Column(name = "completed_at")
    private OffsetDateTime completedAt;

    @Column(name = "success")
    private Boolean success;

    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "error_details", columnDefinition = "jsonb")
    private Map<String, Object> errorDetails;

    @Column(name = "retry_count")
    private Integer retryCount;

    @Column(name = "max_retries")
    private Integer maxRetries;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "output_metrics", columnDefinition = "jsonb")
    private Map<String, Object> outputMetrics;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;


    /* ===== Helper methods cho pipeline ===== */

    public boolean isFinished() {
        return status == ProcessingStatus.READY || status == ProcessingStatus.FAILED;
    }

    public boolean canRetry() {
        if (retryCount == null || maxRetries == null) {
            return false;
        }
        return retryCount < maxRetries;
    }
}
