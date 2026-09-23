package com.poliwise.knowledge.config;

import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MinioConfig {

    private static final Logger log = LoggerFactory.getLogger(MinioConfig.class);

    public static final String BUCKET_NAME = "poliwise-documents";

    @Value("${minio.endpoint:http://localhost:9000}")
    private String endpoint;

    @Value("${minio.public-url:http://localhost:9000}")
    private String publicUrl;

    @Value("${minio.access-key:minioadmin}")
    private String accessKey;

    @Value("${minio.secret-key:minioadmin}")
    private String secretKey;

    @Value("${minio.bucket-name:poliwise-documents}")
    private String bucketName;

    @Bean
    public MinioClient minioClient() {
        MinioClient client = MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();

        initBucket(client);
        return client;
    }

    public String getPublicUrl() {
        return publicUrl;
    }

    private void initBucket(MinioClient client) {
        try {
            boolean exists = client.bucketExists(
                    BucketExistsArgs.builder().bucket(bucketName).build()
            );
            if (!exists) {
                client.makeBucket(MakeBucketArgs.builder().bucket(bucketName).build());
            }
        } catch (Exception e) {
            log.warn("Could not initialize MinIO bucket (may not be available): {}", e.getMessage());
        }
    }
}