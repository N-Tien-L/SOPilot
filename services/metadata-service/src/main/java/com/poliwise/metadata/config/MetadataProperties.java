package com.poliwise.metadata.config;

import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

@Configuration
@EnableScheduling
@ConfigurationPropertiesScan
public class MetadataProperties {
    // Scheduling config is handled via application.properties
}