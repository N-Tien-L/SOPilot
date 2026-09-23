package com.poliwise.knowledge.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class EmbeddingConfig {

    @Value("${knowledge.embedding.api-url:https://api.openai.com/v1/embeddings}")
    private String apiUrl;

    @Value("${knowledge.embedding.api-key:}")
    private String apiKey;

    @Bean
    public WebClient embeddingWebClient() {
        return WebClient.builder()
                .baseUrl(apiUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + apiKey)
                .build();
    }
}