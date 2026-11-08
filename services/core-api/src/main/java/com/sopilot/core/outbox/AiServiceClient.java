package com.sopilot.core.outbox;

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

    Result send(OutboxEvent event);
}
