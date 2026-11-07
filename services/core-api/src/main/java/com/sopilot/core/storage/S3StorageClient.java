package com.sopilot.core.storage;

import com.sopilot.core.config.StorageProperties;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3Configuration;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Request;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;

import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * S3-compatible storage (MinIO locally). The client is built on first use, so a service without
 * storage settings still starts; only document operations fail, with a fixed error.
 */
@Component
public class S3StorageClient implements StorageClient {

    private final StorageProperties properties;
    private volatile S3Client client;
    private volatile S3Presigner presigner;

    public S3StorageClient(StorageProperties properties) {
        this.properties = properties;
    }

    @Override
    public void put(String key, byte[] content, String contentType) {
        s3().putObject(PutObjectRequest.builder().bucket(properties.bucket()).key(key).contentType(contentType)
                .build(), RequestBody.fromBytes(content));
    }

    @Override
    public void delete(String key) {
        s3().deleteObject(DeleteObjectRequest.builder().bucket(properties.bucket()).key(key).build());
    }

    @Override
    public String presignGet(String key, String downloadName, Duration ttl) {
        String disposition = "attachment; filename*=UTF-8''"
                + URLEncoder.encode(downloadName, StandardCharsets.UTF_8).replace("+", "%20");
        GetObjectRequest get = GetObjectRequest.builder().bucket(properties.bucket()).key(key)
                .responseContentDisposition(disposition).build();
        return presigner().presignGetObject(GetObjectPresignRequest.builder().signatureDuration(ttl)
                .getObjectRequest(get).build()).url().toString();
    }

    @Override
    public List<StoredObject> list(String prefix, int max) {
        List<StoredObject> found = new ArrayList<>();
        var pages = s3().listObjectsV2Paginator(ListObjectsV2Request.builder().bucket(properties.bucket())
                .prefix(prefix).build());
        for (var page : pages) {
            for (var object : page.contents()) {
                found.add(new StoredObject(object.key(), object.lastModified()));
                if (found.size() >= max) {
                    return found;
                }
            }
        }
        return found;
    }

    private S3Client s3() {
        S3Client local = client;
        if (local == null) {
            synchronized (this) {
                if (client == null) {
                    requireConfigured();
                    client = S3Client.builder().endpointOverride(URI.create(properties.endpoint()))
                            .region(Region.of(properties.region())).credentialsProvider(credentials())
                            .serviceConfiguration(S3Configuration.builder().pathStyleAccessEnabled(true).build())
                            .build();
                }
                local = client;
            }
        }
        return local;
    }

    private S3Presigner presigner() {
        S3Presigner local = presigner;
        if (local == null) {
            synchronized (this) {
                if (presigner == null) {
                    requireConfigured();
                    presigner = S3Presigner.builder().endpointOverride(URI.create(properties.endpoint()))
                            .region(Region.of(properties.region())).credentialsProvider(credentials())
                            .serviceConfiguration(S3Configuration.builder().pathStyleAccessEnabled(true).build())
                            .build();
                }
                local = presigner;
            }
        }
        return local;
    }

    private StaticCredentialsProvider credentials() {
        return StaticCredentialsProvider.create(
                AwsBasicCredentials.create(properties.accessKey(), properties.secretKey()));
    }

    private void requireConfigured() {
        if (!properties.configured()) {
            throw new IllegalStateException("Object storage is not configured (SOPILOT_S3_*)");
        }
    }
}
