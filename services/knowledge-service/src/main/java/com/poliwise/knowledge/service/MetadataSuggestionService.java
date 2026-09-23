package com.poliwise.knowledge.service;

import com.poliwise.knowledge.config.KnowledgeProperties;
import com.poliwise.knowledge.dto.MetadataSuggestionRequest;
import com.poliwise.knowledge.dto.MetadataSuggestionResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

/**
 * Calls ingestion-service POST /api/v1/metadata/suggest to get AI-suggested metadata.
 * Implements fallback: returns null on timeout or error so UI can prompt manual entry.
 */
@Service
public class MetadataSuggestionService {

    private static final Logger log = LoggerFactory.getLogger(MetadataSuggestionService.class);

    private final WebClient ingestionWebClient;
    private final KnowledgeProperties properties;

    public MetadataSuggestionService(
            WebClient ingestionWebClient,
            KnowledgeProperties properties) {
        this.ingestionWebClient = ingestionWebClient;
        this.properties = properties;
    }

    /**
     * Request metadata suggestion from ingestion-service.
     *
     * @param request the suggestion request payload
     * @return suggested metadata, or null if ingestion-service is unavailable
     */
    public MetadataSuggestionResponse suggest(MetadataSuggestionRequest request) {
        int timeoutSeconds = properties.getIngestion().getSuggestionTimeoutSeconds();

        try {
            return ingestionWebClient.post()
                    .uri("/api/v1/metadata/suggest")
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(MetadataSuggestionResponse.class)
                    .timeout(Duration.ofSeconds(timeoutSeconds))
                    .block();
        } catch (Exception e) {
            log.warn("Metadata suggestion unavailable, falling back to manual entry: {}", e.getMessage());
            return null;
        }
    }
}
