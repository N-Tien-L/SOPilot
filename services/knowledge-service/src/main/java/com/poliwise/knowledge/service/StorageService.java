package com.poliwise.knowledge.service;

import com.poliwise.knowledge.config.MinioConfig;
import io.minio.*;
import io.minio.http.Method;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

@Service
public class StorageService {

    private static final Logger log = LoggerFactory.getLogger(StorageService.class);

    private final MinioClient minioClient;
    private final String bucketName;
    private final String minioPublicUrl;

    public StorageService(MinioClient minioClient, MinioConfig minioConfig) {
        this.minioClient = minioClient;
        this.bucketName = MinioConfig.BUCKET_NAME;
        this.minioPublicUrl = minioConfig.getPublicUrl();
    }

    public String uploadFile(MultipartFile file, UUID documentId) {
        String extension = getExtension(file.getOriginalFilename());
        String fileKey = "documents/" + documentId + "/" + System.currentTimeMillis() + "." + extension;

        try {
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .stream(file.getInputStream(), file.getSize(), -1)
                            .contentType(file.getContentType())
                            .build()
            );
            log.debug("Uploaded file to MinIO: bucket={}, key={}", bucketName, fileKey);
            return fileKey;
        } catch (Exception e) {
            log.error("Failed to upload file to MinIO: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to upload file: " + e.getMessage(), e);
        }
    }

    public String uploadFile(byte[] bytes, String filename, UUID documentId) {
        String extension = getExtension(filename);
        String fileKey = "documents/" + documentId + "/" + System.currentTimeMillis() + "." + extension;
        String contentType = getContentType(extension);

        try {
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .stream(new java.io.ByteArrayInputStream(bytes), bytes.length, -1)
                            .contentType(contentType)
                            .build()
            );
            log.debug("Uploaded byte array to MinIO: bucket={}, key={}", bucketName, fileKey);
            return fileKey;
        } catch (Exception e) {
            log.error("Failed to upload bytes to MinIO: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to upload file: " + e.getMessage(), e);
        }
    }

    public void uploadConflictFile(byte[] bytes, String fileKey) {
        String extension = getExtension(fileKey);
        String contentType = getContentType(extension);

        try {
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .stream(new java.io.ByteArrayInputStream(bytes), bytes.length, -1)
                            .contentType(contentType)
                            .build()
            );
            log.debug("Uploaded conflict file to MinIO: bucket={}, key={}", bucketName, fileKey);
        } catch (Exception e) {
            log.error("Failed to upload conflict file to MinIO: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to upload conflict file: " + e.getMessage(), e);
        }
    }

    public boolean conflictFileExists(String fileKey) {
        try {
            minioClient.statObject(
                    StatObjectArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .build()
            );
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public long getFileSize(String fileKey) {
        try {
            return minioClient.statObject(
                    StatObjectArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .build()
            ).size();
        } catch (Exception e) {
            return 0;
        }
    }

    public InputStream downloadFile(String fileKey) {
        try {
            return minioClient.getObject(
                    GetObjectArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .build()
            );
        } catch (Exception e) {
            log.error("Failed to download file from MinIO: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to download file: " + e.getMessage(), e);
        }
    }

    public void deleteFile(String fileKey) {
        try {
            minioClient.removeObject(
                    RemoveObjectArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .build()
            );
            log.debug("Deleted file from MinIO: bucket={}, key={}", bucketName, fileKey);
        } catch (Exception e) {
            log.error("Failed to delete file from MinIO: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to delete file: " + e.getMessage(), e);
        }
    }

    private String getFileUrlInternal(String fileKey, String baseUrl) {
        try {
            String presigned = minioClient.getPresignedObjectUrl(
                    GetPresignedObjectUrlArgs.builder()
                            .bucket(bucketName)
                            .object(fileKey)
                            .method(Method.GET)
                            .expiry(3600) // 1 hour
                            .build()
            );
            return presigned.replaceFirst(
                    "http://[^/]+",
                    baseUrl.replaceAll("/$", ""));
        } catch (Exception e) {
            log.error("Failed to generate presigned URL: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to generate file URL: " + e.getMessage(), e);
        }
    }

    /**
     * Public URL — for browser access (uses localhost:9000).
     */
    public String getFileUrl(String fileKey) {
        return getFileUrlInternal(fileKey, minioPublicUrl);
    }

    public String readFileContent(String fileKey) {
        try (InputStream is = minioClient.getObject(
                GetObjectArgs.builder()
                        .bucket(bucketName)
                        .object(fileKey)
                        .build())) {
            return new String(is.readAllBytes(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            log.error("Failed to read file content from MinIO: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to read file content: " + e.getMessage(), e);
        }
    }

    private String getExtension(String filename) {
        if (filename == null || !filename.contains(".")) {
            return "bin";
        }
        return filename.substring(filename.lastIndexOf('.') + 1).toLowerCase();
    }

    private String getContentType(String extension) {
        return switch (extension.toLowerCase()) {
            case "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
            case "xlsx" -> "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
            case "pptx" -> "application/vnd.openxmlformats-officedocument.presentationml.presentation";
            case "doc"  -> "application/msword";
            case "pdf"  -> "application/pdf";
            default      -> "application/octet-stream";
        };
    }
}
