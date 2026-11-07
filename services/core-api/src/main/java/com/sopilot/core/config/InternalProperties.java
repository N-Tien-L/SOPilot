package com.sopilot.core.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * Service-to-service settings (TECH-V2-core-api §8, §9). {@code token} guards {@code /internal/**}
 * in both directions; a blank token rejects every internal call (fail closed).
 */
@ConfigurationProperties(prefix = "sopilot.internal")
public record InternalProperties(@DefaultValue("") String token,
                                 @DefaultValue("http://ai-service:8000") String aiBaseUrl) {

    @Override
    public String toString() {
        return "InternalProperties[token=<redacted>, aiBaseUrl=" + aiBaseUrl + "]";
    }
}
