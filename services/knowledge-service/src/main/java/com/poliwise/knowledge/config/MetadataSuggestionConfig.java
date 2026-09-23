package com.poliwise.knowledge.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class MetadataSuggestionConfig {

    private final KnowledgeProperties properties;

    public MetadataSuggestionConfig(KnowledgeProperties properties) {
        this.properties = properties;
    }

    @Bean
    public WebClient ingestionWebClient() {
        return WebClient.builder()
                .baseUrl(properties.getIngestion().getApiUrl())
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader("X-Internal-API-Key", properties.getIngestion().getInternalApiKey())
                .build();
    }

    @Bean
    public WebClient metadataWebClient() {
        return WebClient.builder()
                .baseUrl(properties.getMetadata().getApiUrl())
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }
}
