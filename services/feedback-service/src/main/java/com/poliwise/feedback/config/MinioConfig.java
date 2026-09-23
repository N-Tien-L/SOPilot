package com.poliwise.feedback.config;

import io.minio.MinioClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MinioConfig {

    @Value("${MINIO_ENDPOINT:http://localhost:9000}")
    private String endpoint;

    @Value("${MINIO_ACCESS_KEY:minioadmin}")
    private String accessKey;

    @Value("${MINIO_SECRET_KEY:minioadmin}")
    private String secretKey;

    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
    }
}
