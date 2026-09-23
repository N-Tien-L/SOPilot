package com.poliwise.knowledge.config;

import com.poliwise.knowledge.enums.ChunkingStrategy;
import com.poliwise.knowledge.enums.EmbeddingModel;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@ConfigurationProperties(prefix = "knowledge")
public class KnowledgeProperties {

    private Chunking chunking = new Chunking();
    private Embedding embedding = new Embedding();
    private FileValidation fileValidation = new FileValidation();
    private Processing processing = new Processing();
    private Ingestion ingestion = new Ingestion();
    private Metadata metadata = new Metadata();
    private Staging staging = new Staging();

    public Chunking getChunking() { return chunking; }
    public void setChunking(Chunking chunking) { this.chunking = chunking; }
    public Embedding getEmbedding() { return embedding; }
    public void setEmbedding(Embedding embedding) { this.embedding = embedding; }
    public FileValidation getFileValidation() { return fileValidation; }
    public void setFileValidation(FileValidation fileValidation) { this.fileValidation = fileValidation; }
    public Processing getProcessing() { return processing; }
    public void setProcessing(Processing processing) { this.processing = processing; }
    public Ingestion getIngestion() { return ingestion; }
    public void setIngestion(Ingestion ingestion) { this.ingestion = ingestion; }
    public Metadata getMetadata() { return metadata; }
    public void setMetadata(Metadata metadata) { this.metadata = metadata; }
    public Staging getStaging() { return staging; }
    public void setStaging(Staging staging) { this.staging = staging; }

    public static class Chunking {
        private ChunkingStrategy defaultStrategy = ChunkingStrategy.RECURSIVE;
        private int defaultChunkSize = 1000;
        private int defaultOverlap = 200;

        public ChunkingStrategy getDefaultStrategy() { return defaultStrategy; }
        public void setDefaultStrategy(ChunkingStrategy defaultStrategy) { this.defaultStrategy = defaultStrategy; }
        public int getDefaultChunkSize() { return defaultChunkSize; }
        public void setDefaultChunkSize(int defaultChunkSize) { this.defaultChunkSize = defaultChunkSize; }
        public int getDefaultOverlap() { return defaultOverlap; }
        public void setDefaultOverlap(int defaultOverlap) { this.defaultOverlap = defaultOverlap; }
    }

    public static class Embedding {
        private EmbeddingModel defaultModel = EmbeddingModel.TEXT_EMBEDDING_3_SMALL;
        private String apiUrl = "https://api.openai.com/v1/embeddings";
        private String apiKey;
        private int batchSize = 100;

        public EmbeddingModel getDefaultModel() { return defaultModel; }
        public void setDefaultModel(EmbeddingModel defaultModel) { this.defaultModel = defaultModel; }
        public String getApiUrl() { return apiUrl; }
        public void setApiUrl(String apiUrl) { this.apiUrl = apiUrl; }
        public String getApiKey() { return apiKey; }
        public void setApiKey(String apiKey) { this.apiKey = apiKey; }
        public int getBatchSize() { return batchSize; }
        public void setBatchSize(int batchSize) { this.batchSize = batchSize; }
    }

    public static class FileValidation {
        private long maxFileSizeBytes = 50 * 1024 * 1024L; // 50MB
        private String[] allowedExtensions = {"pdf", "docx", "xlsx", "doc", "xls", "txt", "png", "jpg", "jpeg"};

        public long getMaxFileSizeBytes() { return maxFileSizeBytes; }
        public void setMaxFileSizeBytes(long maxFileSizeBytes) { this.maxFileSizeBytes = maxFileSizeBytes; }
        public String[] getAllowedExtensions() { return allowedExtensions; }
        public void setAllowedExtensions(String[] allowedExtensions) { this.allowedExtensions = allowedExtensions; }
    }

    public static class Processing {
        private int maxRetries = 3;
        private int retryDelaySeconds = 30;

        public int getMaxRetries() { return maxRetries; }
        public void setMaxRetries(int maxRetries) { this.maxRetries = maxRetries; }
        public int getRetryDelaySeconds() { return retryDelaySeconds; }
        public void setRetryDelaySeconds(int retryDelaySeconds) { this.retryDelaySeconds = retryDelaySeconds; }
    }

    public static class Ingestion {
        private String apiUrl = "http://localhost:8088";
        private String internalApiKey;
        private int suggestionTimeoutSeconds = 30;

        public String getInternalApiKey() { return internalApiKey; }
        public void setInternalApiKey(String internalApiKey) { this.internalApiKey = internalApiKey; }
        public String getApiUrl() { return apiUrl; }
        public void setApiUrl(String apiUrl) { this.apiUrl = apiUrl; }
        public int getSuggestionTimeoutSeconds() { return suggestionTimeoutSeconds; }
        public void setSuggestionTimeoutSeconds(int suggestionTimeoutSeconds) { this.suggestionTimeoutSeconds = suggestionTimeoutSeconds; }
    }

    public static class Metadata {
        private String apiUrl = "http://localhost:8084";

        public String getApiUrl() { return apiUrl; }
        public void setApiUrl(String apiUrl) { this.apiUrl = apiUrl; }
    }

    public static class Staging {
        private int ttlMinutes = 30;

        public int getTtlMinutes() { return ttlMinutes; }
        public void setTtlMinutes(int ttlMinutes) { this.ttlMinutes = ttlMinutes; }
    }
}