package com.sopilot.core.support;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

/** Replaces S3 and the ai-service HTTP client so API-level tests stay in-process. */
@TestConfiguration
public class TestBeans {

    @Bean
    @Primary
    public InMemoryStorage inMemoryStorage() {
        return new InMemoryStorage();
    }

    @Bean
    @Primary
    public RecordingAiClient recordingAiClient() {
        return new RecordingAiClient();
    }
}
