package com.sopilot.core.outbox;

import java.time.Duration;

/** Delivers an outbox event to ai-service (TECH-V2-core-api §8.1). */
public interface AiServiceClient {

    /**
     * @param status HTTP status, or {@code -1} when no response arrived (connect/timeout error)
     * @param error  short, non-sensitive reason for the log and {@code outbox_events.last_error}
     */
    record Result(int status, String error) {
        public boolean delivered() {
            return status >= 200 && status < 300;
        }

        /** 5xx, 408, 429 and network failures are retried; any other 4xx is a contract error. */
        public boolean retryable() {
            return status == -1 || status >= 500 || status == 408 || status == 429;
        }
    }

    /** Request timeout of the background dispatcher. */
    Duration DEFAULT_TIMEOUT = Duration.ofSeconds(10);

    default Result send(OutboxEvent event) {
        return send(event, DEFAULT_TIMEOUT);
    }

    /** Same as {@link #send(OutboxEvent)} with a caller-chosen request timeout (the 2 s direct send of TECH §2.3). */
    Result send(OutboxEvent event, Duration timeout);
}
