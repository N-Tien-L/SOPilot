package com.poliwise.knowledge.client;

import com.poliwise.knowledge.dto.ConfirmResultResponse;
import com.poliwise.knowledge.dto.DocumentDuplicateInfo;
import com.poliwise.knowledge.dto.DuplicateCheckResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.Map;
import java.util.UUID;

@Component
public class IngestionServiceClient {

    private static final Logger log = LoggerFactory.getLogger(IngestionServiceClient.class);
    private static final Duration TIMEOUT = Duration.ofSeconds(10);

    private final WebClient ingestionWebClient;

    public IngestionServiceClient(@Value("${knowledge.ingestion.api-url}") String ingestionApiUrl) {
        this.ingestionWebClient = WebClient.builder()
                .baseUrl(ingestionApiUrl)
                .build();
    }

    /**
     * Check for duplicates using file checksum via ingestion-service.
     * Returns a DuplicateCheckResponse with duplicate info if found.
     */
    @SuppressWarnings("unchecked")
    public DuplicateCheckResponse checkDuplicateByChecksum(String checksum) {
        try {
            Map<String, Object> response = ingestionWebClient.get()
                    .uri("/api/v1/check-duplicate?checksum={checksum}", checksum)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(TIMEOUT)
                    .block();

            if (response == null) {
                return DuplicateCheckResponse.notDuplicate();
            }

            boolean isDuplicate = Boolean.TRUE.equals(response.get("is_duplicate"))
                    || Boolean.TRUE.equals(response.get("isDuplicate"));
            if (!isDuplicate) {
                return DuplicateCheckResponse.notDuplicate();
            }

            String action = (String) response.get("action");
            String detectionMethod = (String) response.get("detection_method");
            if (detectionMethod == null) detectionMethod = (String) response.get("detectionMethod");
            Double similarity = response.get("similarity") instanceof Number
                    ? ((Number) response.get("similarity")).doubleValue()
                    : null;

            DocumentDuplicateInfo existingDoc = null;
            Object existingRaw = response.get("existing_document");
            if (existingRaw == null) existingRaw = response.get("existingDocument");
            if (existingRaw instanceof Map) {
                Map<String, Object> docMap = (Map<String, Object>) existingRaw;
                String docIdStr = (String) docMap.get("document_id");
                if (docIdStr == null) docIdStr = (String) docMap.get("documentId");
                Object fileSizeRaw = docMap.get("file_size_bytes");
                if (fileSizeRaw == null) fileSizeRaw = docMap.get("fileSizeBytes");
                existingDoc = new DocumentDuplicateInfo(
                        docIdStr != null ? UUID.fromString(docIdStr) : null,
                        (String) docMap.get("original_filename"),
                        fileSizeRaw != null ? ((Number) fileSizeRaw).longValue() : null,
                        null,
                        (String) docMap.get("title"),
                        (String) docMap.get("category_slug"),
                        (String) docMap.get("status"),
                        (String) docMap.get("file_checksum")
                );
            }

            DuplicateCheckResponse.BlockAction blockAction = "BLOCK".equals(action)
                    ? DuplicateCheckResponse.BlockAction.BLOCK
                    : DuplicateCheckResponse.BlockAction.SUGGEST_VERSION;

            return new DuplicateCheckResponse(true, blockAction.name(), existingDoc, similarity, detectionMethod);
        } catch (Exception e) {
            log.warn("Failed to check duplicate via ingestion-service: {}", e.getMessage());
            return DuplicateCheckResponse.notDuplicate();
        }
    }

    /**
     * Get job status from ingestion-service for sync polling.
     */
    @SuppressWarnings("unchecked")
    public SyncJobStatus getJobStatus(UUID jobId) {
        try {
            Map<String, Object> response = ingestionWebClient.get()
                    .uri("/api/v1/jobs/{jobId}", jobId)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(TIMEOUT)
                    .block();

            if (response == null) {
                return new SyncJobStatus("UNKNOWN", null, "No response from ingestion-service");
            }

            String status = (String) response.get("status");
            // ingestion-service returns snake_case JSON (output_metrics, error_message).
            Map<String, Object> metrics = null;
            if (response.get("output_metrics") instanceof Map) {
                metrics = (Map<String, Object>) response.get("output_metrics");
            } else if (response.get("outputMetrics") instanceof Map) {
                metrics = (Map<String, Object>) response.get("outputMetrics");
            }
            String errorMessage = (String) response.get("error_message");
            if (errorMessage == null) {
                errorMessage = (String) response.get("errorMessage");
            }

            return new SyncJobStatus(status, metrics, errorMessage);
        } catch (Exception e) {
            log.warn("Failed to get job status for {}: {}", jobId, e.getMessage());
            return new SyncJobStatus("UNKNOWN", null, e.getMessage());
        }
    }

    public record SyncJobStatus(String status, Map<String, Object> outputMetrics, String errorMessage) {
        public boolean isCompleted() {
            // The ingestion-service writes status='READY' on completion (matches
            // knowledge.processing_status enum). 'COMPLETED' is the legacy name.
            return "READY".equals(status) || "COMPLETED".equals(status);
        }

        public boolean isFailed() {
            return "FAILED".equals(status);
        }

        public boolean isSkipped() {
            if (outputMetrics == null) return false;
            return Boolean.TRUE.equals(outputMetrics.get("skipped"));
        }

        public boolean isNearDuplicate() {
            if (outputMetrics == null) return false;
            Object nearDup = outputMetrics.get("near_duplicate");
            if (nearDup instanceof Boolean) return (Boolean) nearDup;
            if (nearDup instanceof Map) return true;
            return false;
        }

        public Double getSimilarity() {
            if (outputMetrics == null) return null;
            // Check top-level similarity first
            Object sim = outputMetrics.get("similarity");
            if (sim instanceof Number) return ((Number) sim).doubleValue();
            // Fallback: check inside near_duplicate object
            Object nearDup = outputMetrics.get("near_duplicate");
            if (nearDup instanceof Map) {
                Map<?, ?> nearDupMap = (Map<?, ?>) nearDup;
                Object nestedSim = nearDupMap.get("similarity");
                if (nestedSim instanceof Number) return ((Number) nestedSim).doubleValue();
                // Also check for 'score' or 'cosine_distance' inside near_duplicate
                Object score = nearDupMap.get("score");
                if (score instanceof Number) return ((Number) score).doubleValue();
                Object distance = nearDupMap.get("cosine_distance");
                if (distance instanceof Number) {
                    // Convert cosine distance to similarity (1 - distance)
                    return 1.0 - ((Number) distance).doubleValue();
                }
            }
            return null;
        }

        public String getMethod() {
            if (outputMetrics == null) return null;
            return (String) outputMetrics.get("method");
        }

        public Integer getChunkCount() {
            if (outputMetrics == null) return null;
            Object count = outputMetrics.get("chunk_count");
            if (count instanceof Number) return ((Number) count).intValue();
            return null;
        }
    }
}
