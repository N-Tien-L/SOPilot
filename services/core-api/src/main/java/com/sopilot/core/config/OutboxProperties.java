package com.sopilot.core.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

import java.time.Duration;

/** Outbox dispatcher (TECH-V2-core-api §7). {@code enabled=false} stops the poller and the after-commit wake-up. */
@ConfigurationProperties(prefix = "sopilot.outbox")
public record OutboxProperties(@DefaultValue("true") boolean enabled,
                               @DefaultValue("PT5S") Duration poll,
                               @DefaultValue("20") int maxAttempts) {
}
