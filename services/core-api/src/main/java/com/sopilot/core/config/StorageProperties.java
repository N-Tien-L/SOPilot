package com.sopilot.core.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/** Object storage through the standard S3 API; one bucket name for every service (TECH §9). */
@ConfigurationProperties(prefix = "sopilot.s3")
public record StorageProperties(@DefaultValue("") String endpoint,
                                @DefaultValue("") String bucket,
                                @DefaultValue("") String accessKey,
                                @DefaultValue("") String secretKey,
                                @DefaultValue("us-east-1") String region,
                                @DefaultValue("") String publicEndpoint) {

    /**
     * The host a browser can reach, used only to sign download URLs. Blank means the same as
     * {@link #endpoint()}; in compose the service endpoint is the internal {@code minio:9000}.
     */
    public String presignEndpoint() {
        return publicEndpoint.isBlank() ? endpoint : publicEndpoint;
    }

    public boolean configured() {
        return !endpoint.isBlank() && !bucket.isBlank() && !accessKey.isBlank() && !secretKey.isBlank();
    }

    @Override
    public String toString() {
        return "StorageProperties[endpoint=" + endpoint + ", publicEndpoint=" + publicEndpoint + ", bucket=" + bucket + ", keys=<redacted>]";
    }
}
