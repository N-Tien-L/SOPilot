package com.sopilot.core.storage;

import com.sopilot.core.config.StorageProperties;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.MinIOContainer;
import org.testcontainers.utility.DockerImageName;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3Configuration;
import software.amazon.awssdk.services.s3.model.CreateBucketRequest;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** The real S3 client against MinIO: write, list, pre-signed download with the original name, delete. */
class S3StorageClientIT {

    private static final String BUCKET = "sopilot-test";
    private static MinIOContainer minio;
    private static S3StorageClient storage;

    @BeforeAll
    static void start() {
        minio = new MinIOContainer(DockerImageName.parse("minio/minio:RELEASE.2024-05-10T01-41-38Z"));
        minio.start();
        try (S3Client admin = S3Client.builder().endpointOverride(URI.create(minio.getS3URL()))
                .region(Region.US_EAST_1)
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(minio.getUserName(), minio.getPassword())))
                .serviceConfiguration(S3Configuration.builder().pathStyleAccessEnabled(true).build()).build()) {
            admin.createBucket(CreateBucketRequest.builder().bucket(BUCKET).build());
        }
        storage = new S3StorageClient(new StorageProperties(minio.getS3URL(), BUCKET, minio.getUserName(),
                minio.getPassword(), "us-east-1"));
    }

    @AfterAll
    static void stop() {
        if (minio != null) {
            minio.stop();
        }
    }

    private static String key() {
        return "workspaces/" + UUID.randomUUID() + "/documents/" + UUID.randomUUID() + "/versions/" + UUID.randomUUID();
    }

    private static HttpResponse<byte[]> fetch(String url) throws Exception {
        return HttpClient.newHttpClient().send(HttpRequest.newBuilder(URI.create(url)).build(),
                HttpResponse.BodyHandlers.ofByteArray());
    }

    @Test
    void putThenDownloadThroughAPresignedUrlWithTheOriginalFileName() throws Exception {
        String key = key();
        byte[] content = "# Quy trình\n".getBytes(StandardCharsets.UTF_8);

        storage.put(key, content, "text/markdown");
        HttpResponse<byte[]> response = fetch(storage.presignGet(key, "Quy trình mua hàng.md", Duration.ofMinutes(5)));

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).isEqualTo(content);
        assertThat(response.headers().firstValue("Content-Disposition").orElse(""))
                .startsWith("attachment; filename*=UTF-8''Quy%20tr%C3%ACnh%20mua%20h%C3%A0ng.md");
    }

    @Test
    void anExpiredUrlIsRefused() throws Exception {
        String key = key();
        storage.put(key, new byte[] {1}, "application/octet-stream");

        String url = storage.presignGet(key, "x.md", Duration.ofSeconds(1));
        Thread.sleep(2500);

        assertThat(fetch(url).statusCode()).isEqualTo(403);
    }

    @Test
    void deleteRemovesTheObjectAndDeletingAgainIsHarmless() throws Exception {
        String key = key();
        storage.put(key, new byte[] {1, 2}, "application/pdf");

        storage.delete(key);
        storage.delete(key);

        assertThat(fetch(storage.presignGet(key, "x.pdf", Duration.ofMinutes(1))).statusCode()).isEqualTo(404);
    }

    @Test
    void listReturnsKeysUnderThePrefixWithTheirAge() {
        String prefix = "workspaces/" + UUID.randomUUID() + "/";
        storage.put(prefix + "a", new byte[] {1}, "application/octet-stream");
        storage.put(prefix + "b", new byte[] {2}, "application/octet-stream");
        storage.put("workspaces/" + UUID.randomUUID() + "/c", new byte[] {3}, "application/octet-stream");

        List<StorageClient.StoredObject> found = storage.list(prefix, 100);

        assertThat(found).extracting(StorageClient.StoredObject::key).containsExactlyInAnyOrder(prefix + "a", prefix + "b");
        assertThat(found).allSatisfy(o -> assertThat(o.lastModified()).isBetween(Instant.now().minusSeconds(120),
                Instant.now().plusSeconds(120)));
        assertThat(storage.list(prefix, 1)).hasSize(1);
    }

    @Test
    void anUnconfiguredClientFailsOnUseNotAtStartup() {
        S3StorageClient unconfigured = new S3StorageClient(new StorageProperties("", "", "", "", "us-east-1"));

        assertThatThrownBy(() -> unconfigured.put("k", new byte[] {1}, "x"))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("SOPILOT_S3_");
    }
}
