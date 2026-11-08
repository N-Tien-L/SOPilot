package com.sopilot.core.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/** Object storage through the standard S3 API; one bucket name for every service (TECH §9). */
@ConfigurationProperties(prefix = "sopilot.s3")
public record StorageProperties(@DefaultValue("") String endpoint,
                                @DefaultValue("") String bucket,
                                @DefaultValue("") String accessKey,
                                @DefaultValue("") String secretKey,
                                @DefaultValue("us-east-1") String region) {

    public boolean configured() {
        return !endpoint.isBlank() && !bucket.isBlank() && !accessKey.isBlank() && !secretKey.isBlank();
    }

    @Override
    public String toString() {
        return "StorageProperties[endpoint=" + endpoint + ", bucket=" + bucket + ", keys=<redacted>]";
    }
}
