package com.poliwise.knowledge.service;

import com.poliwise.knowledge.config.KnowledgeProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Fetches context (active categories, top tags) from metadata-service
 * for use in metadata suggestion requests.
 */
@Service
public class MetadataContextService {

    private static final Logger log = LoggerFactory.getLogger(MetadataContextService.class);

    private final WebClient metadataWebClient;
    private final KnowledgeProperties properties;

    public MetadataContextService(
            WebClient metadataWebClient,
            KnowledgeProperties properties) {
        this.metadataWebClient = metadataWebClient;
        this.properties = properties;
    }

    /**
     * Fetch active category slugs from metadata-service.
     *
     * @return list of active category slugs, empty list on failure
     */
    public List<String> fetchActiveCategorySlugs() {
        try {
            List<Map<String, Object>> categories = metadataWebClient.get()
                    .uri("/api/v1/categories/active")
                    .retrieve()
                    .bodyToMono(List.class)
                    .timeout(Duration.ofSeconds(3))
                    .block();

            if (categories == null) {
                return Collections.emptyList();
            }

            return categories.stream()
                    .map(cat -> (String) cat.get("slug"))
                    .filter(slug -> slug != null && !slug.isEmpty())
                    .toList();
        } catch (Exception e) {
            log.warn("Failed to fetch active categories: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    /**
     * Fetch top tag names from metadata-service.
     *
     * @return list of top tag names, empty list on failure
     */
    public List<String> fetchTopTagNames(int limit) {
        try {
            List<Map<String, Object>> tags = metadataWebClient.get()
                    .uri("/api/v1/tags/popular")
                    .retrieve()
                    .bodyToMono(List.class)
                    .timeout(Duration.ofSeconds(3))
                    .block();

            if (tags == null) {
                return Collections.emptyList();
            }

            return tags.stream()
                    .map(tag -> (String) tag.get("name"))
                    .filter(name -> name != null && !name.isEmpty())
                    .limit(limit)
                    .toList();
        } catch (Exception e) {
            log.warn("Failed to fetch top tags: {}", e.getMessage());
            return Collections.emptyList();
        }
    }
}
