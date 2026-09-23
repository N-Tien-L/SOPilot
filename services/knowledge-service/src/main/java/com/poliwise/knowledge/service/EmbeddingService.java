package com.poliwise.knowledge.service;

import com.poliwise.knowledge.config.KnowledgeProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.List;

@Service
public class EmbeddingService {

    private static final Logger log = LoggerFactory.getLogger(EmbeddingService.class);

    private final WebClient webClient;
    private final KnowledgeProperties properties;

    public EmbeddingService(WebClient embeddingWebClient, KnowledgeProperties properties) {
        this.webClient = embeddingWebClient;
        this.properties = properties;
    }

    public List<Double> generateEmbedding(String text) {
        // Placeholder implementation
        // In production, this would call the actual embedding API
        // using OpenAI, HuggingFace, or a self-hosted model

        return List.of(0.0); // Placeholder
    }

    public List<List<Double>> generateEmbeddings(List<String> texts) {
        log.debug("Generating embeddings for {} texts", texts.size());
        return texts.stream()
                .map(this::generateEmbedding)
                .toList();
    }
}