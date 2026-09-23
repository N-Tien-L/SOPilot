package com.poliwise.knowledge.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.*;

/**
 * Synchronous REST client for communicating with metadata-service.
 * Used during Phase 1 confirm flow to:
 *   1. Resolve category_slug → category_id (UUID)
 *   2. Resolve tag names → tag_ids (find-or-create)
 *   3. Create document_metadata record
 *
 * Forwards the current user's JWT token for authenticated endpoints.
 */
@Component
public class MetadataServiceClient {

    private static final Logger log = LoggerFactory.getLogger(MetadataServiceClient.class);
    private static final Duration TIMEOUT = Duration.ofSeconds(5);

    private final WebClient metadataWebClient;

    public MetadataServiceClient(WebClient metadataWebClient) {
        this.metadataWebClient = metadataWebClient;
    }

    /**
     * Extract the Authorization header from the current HTTP request context.
     * This allows service-to-service calls to forward the user's JWT.
     */
    private String getCurrentAuthToken() {
        try {
            ServletRequestAttributes attrs =
                    (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
            if (attrs != null) {
                String auth = attrs.getRequest().getHeader("Authorization");
                if (auth != null && auth.startsWith("Bearer ")) {
                    return auth;
                }
            }
        } catch (Exception e) {
            log.debug("Could not extract Authorization header: {}", e.getMessage());
        }
        return null;
    }

    /**
     * Resolve a category slug to its UUID via GET /api/v1/categories/active.
     * This endpoint is permitAll in metadata-service — no auth needed.
     */
    public UUID resolveCategorySlug(String slug) {
        if (slug == null || slug.isBlank()) {
            return null;
        }
        try {
            List<com.poliwise.knowledge.dto.CategoryResponse> categories = metadataWebClient.get()
                    .uri("/api/v1/categories/active")
                    .retrieve()
                    .bodyToFlux(com.poliwise.knowledge.dto.CategoryResponse.class)
                    .collectList()
                    .timeout(TIMEOUT)
                    .block();

            if (categories == null) return null;

            return categories.stream()
                    .filter(cat -> slug.equalsIgnoreCase(cat.slug()))
                    .map(com.poliwise.knowledge.dto.CategoryResponse::id)
                    .findFirst()
                    .orElse(null);
        } catch (Exception e) {
            log.warn("Failed to resolve category slug '{}': {}", slug, e.getMessage());
            return null;
        }
    }

    /**
     * Resolve tag names to UUIDs. Uses bulk resolution API in metadata-service.
     * Creates new tags in metadata-service if they don't exist.
     * POST /api/v1/tags/resolve requires auth (forwarded JWT).
     */
    public List<UUID> resolveTagNames(List<String> tagNames) {
        if (tagNames == null || tagNames.isEmpty()) {
            return Collections.emptyList();
        }

        String authToken = getCurrentAuthToken();

        try {
            WebClient.RequestBodySpec requestSpec = metadataWebClient.post()
                    .uri("/api/v1/tags/resolve");

            if (authToken != null) {
                requestSpec = (WebClient.RequestBodySpec) requestSpec.header("Authorization", authToken);
            }

            com.poliwise.knowledge.dto.ResolveTagsResponse response = requestSpec
                    .bodyValue(Map.of("tagNames", tagNames))
                    .retrieve()
                    .bodyToMono(com.poliwise.knowledge.dto.ResolveTagsResponse.class)
                    .timeout(TIMEOUT)
                    .block();

            if (response != null && response.tagIds() != null) {
                log.info("Resolved {} tags (including potential auto-creation)", response.tagIds().size());
                return response.tagIds();
            }
        } catch (Exception e) {
            log.warn("Failed to resolve tags in bulk: {}", e.getMessage());
        }

        return Collections.emptyList();
    }

    /**
     * Create a document metadata record in metadata-service
     * (POST /api/v1/metadata — requires ADMIN).
     */
    @SuppressWarnings("unchecked")
    public void createDocumentMetadata(UUID documentId, String title, String description,
                                       UUID categoryId, List<UUID> tagIds, Boolean isPolicy) {
        String authToken = getCurrentAuthToken();

        try {
            Map<String, Object> body = new HashMap<>();
            body.put("documentId", documentId.toString());
            body.put("title", title);
            body.put("description", description);
            body.put("categoryId", categoryId != null ? categoryId.toString() : null);
            body.put("accessLevel", "PUBLIC");
            body.put("documentType", isPolicy != null && isPolicy ? "POLICY" : "GENERAL");
            if (tagIds != null && !tagIds.isEmpty()) {
                body.put("tagIds", tagIds.stream().map(UUID::toString).toList());
            }

            WebClient.RequestBodySpec req = metadataWebClient.post()
                    .uri("/api/v1/metadata");

            if (authToken != null) {
                req = (WebClient.RequestBodySpec) req.header("Authorization", authToken);
            }

            Map<String, Object> response = req
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(TIMEOUT)
                    .block();

            log.info("Created document metadata in metadata-service: documentId={}, metadataId={}",
                    documentId, response != null ? response.get("id") : "unknown");
        } catch (Exception e) {
            log.error("Failed to create document metadata for documentId={}: {}",
                    documentId, e.getMessage(), e);
            throw new RuntimeException("Failed to save metadata: " + e.getMessage(), e);
        }
    }

    /**
     * Check if the current user has access to a specific document.
     * Returns a map with "documentId", "hasAccess", and "reason".
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> checkDocumentAccess(UUID documentId) {
        String authToken = getCurrentAuthToken();

        try {
            WebClient.RequestHeadersSpec<?> requestSpec = metadataWebClient.get()
                    .uri("/api/v1/access-rules/check/{documentId}", documentId);

            if (authToken != null) {
                requestSpec = requestSpec.header("Authorization", authToken);
            }

            Map<String, Object> response = ((WebClient.RequestHeadersSpec<?>) requestSpec)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(TIMEOUT)
                    .block();

            log.debug("Access check for document {}: hasAccess={}",
                    documentId, response != null ? response.get("hasAccess") : "unknown");
            return response;
        } catch (Exception e) {
            log.warn("Failed to check document access for documentId={}: {}",
                    documentId, e.getMessage());
            // Default to denying access on error for security
            return Map.of(
                    "documentId", documentId.toString(),
                    "hasAccess", false,
                    "reason", "Access check failed: " + e.getMessage()
            );
        }
    }

    /**
     * Filter a list of document IDs to return only those the current user can access.
     * Returns a list of accessible document IDs.
     */
    @SuppressWarnings("unchecked")
    public Set<UUID> filterAccessibleDocuments(List<UUID> documentIds) {
        if (documentIds == null || documentIds.isEmpty()) {
            return Collections.emptySet();
        }

        String authToken = getCurrentAuthToken();

        try {
            Map<String, Object> body = Map.of(
                    "documentIds", documentIds.stream().map(UUID::toString).toList()
            );

            WebClient.RequestBodySpec requestSpec = metadataWebClient.post()
                    .uri("/api/v1/access-rules/filter-accessible");

            if (authToken != null) {
                requestSpec = requestSpec.header("Authorization", authToken);
            }

            Map<String, Object> response = requestSpec
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(TIMEOUT)
                    .block();

            if (response != null && response.get("accessibleDocumentIds") != null) {
                List<String> accessibleIds = (List<String>) response.get("accessibleDocumentIds");
                Set<UUID> accessibleSet = accessibleIds.stream()
                        .map(UUID::fromString)
                        .collect(java.util.stream.Collectors.toSet());

                log.debug("Filtered {} documents: {} accessible",
                        documentIds.size(), accessibleSet.size());
                return accessibleSet;
            }

            log.warn("Unexpected response from filter-accessible endpoint");
            return Collections.emptySet();
        } catch (Exception e) {
            log.warn("Failed to filter accessible documents: {}. Returning empty set for security.",
                    e.getMessage());
            // Default to empty set on error - this means no documents are accessible
            return Collections.emptySet();
        }
    }

    /**
     * Returns access metadata for the ingestion pipeline.
     * Fetches the access rule for the given document and returns it as a Map.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getIngestionAccessMetadata(UUID documentId, UUID requestingUserId) {
        try {
            Map<String, Object> accessResponse = checkDocumentAccess(documentId);
            Map<String, Object> metadata = new HashMap<>();
            metadata.put("documentId", documentId.toString());
            if (accessResponse != null) {
                metadata.put("hasAccess", accessResponse.getOrDefault("hasAccess", false));
                metadata.put("accessLevel", accessResponse.getOrDefault("accessLevel", "UNKNOWN"));
                metadata.put("allowedDepartments", accessResponse.getOrDefault("allowedDepartments", Collections.emptyList()));
                metadata.put("allowedRoles", accessResponse.getOrDefault("allowedRoles", Collections.emptyList()));
                metadata.put("requestingUserId", requestingUserId != null ? requestingUserId.toString() : null);
            }
            return metadata;
        } catch (Exception e) {
            log.warn("Failed to get ingestion access metadata for documentId={}: {}", documentId, e.getMessage());
            return Map.of(
                    "documentId", documentId.toString(),
                    "hasAccess", false,
                    "accessLevel", "UNKNOWN",
                    "allowedDepartments", Collections.emptyList(),
                    "allowedRoles", Collections.emptyList(),
                    "requestingUserId", requestingUserId != null ? requestingUserId.toString() : null
            );
        }
    }

    /**
     * Asserts the current user can read the given document.
     * Throws a RuntimeException if access is denied.
     */
    public void assertCanReadDocument(UUID documentId) {
        Map<String, Object> accessResponse = checkDocumentAccess(documentId);
        Boolean hasAccess = accessResponse != null ? (Boolean) accessResponse.getOrDefault("hasAccess", false) : false;
        if (!hasAccess) {
            String reason = accessResponse != null
                    ? (String) accessResponse.getOrDefault("reason", "Access denied")
                    : "Access check failed";
            throw new RuntimeException("Access denied to document " + documentId + ": " + reason);
        }
    }

    /**
     * Get document title from metadata-service by documentId.
     */
    @SuppressWarnings("unchecked")
    public String getDocumentTitle(UUID documentId) {
        try {
            Map<String, Object> response = metadataWebClient.get()
                    .uri("/api/v1/metadata/{documentId}", documentId)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(TIMEOUT)
                    .block();
            if (response != null && response.get("title") != null) {
                return response.get("title").toString();
            }
        } catch (Exception e) {
            log.warn("Failed to get document title for {}: {}", documentId, e.getMessage());
        }
        return null;
    }

    /**
     * Get document category slug from metadata-service by documentId.
     */
    @SuppressWarnings("unchecked")
    public String getDocumentCategorySlug(UUID documentId) {
        try {
            Map<String, Object> response = metadataWebClient.get()
                    .uri("/api/v1/metadata/{documentId}", documentId)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(TIMEOUT)
                    .block();
            if (response != null && response.get("category") != null) {
                Map<String, Object> category = (Map<String, Object>) response.get("category");
                if (category != null && category.get("slug") != null) {
                    return category.get("slug").toString();
                }
            }
        } catch (Exception e) {
            log.warn("Failed to get document category slug for {}: {}", documentId, e.getMessage());
        }
        return null;
    }
}
