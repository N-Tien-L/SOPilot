package com.sopilot.core.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * Per-workspace document quota (FR-09, owner decision 2026-10-21): 50 documents / 200 MB by
 * default, {@code 0} disables a limit. Question quotas belong to ai-service.
 */
@ConfigurationProperties(prefix = "sopilot.quota")
public record QuotaProperties(@DefaultValue("50") long docsPerWorkspace,
                              @DefaultValue("209715200") long bytesPerWorkspace) {
}
