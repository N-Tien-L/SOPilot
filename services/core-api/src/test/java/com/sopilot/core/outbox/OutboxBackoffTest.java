package com.sopilot.core.outbox;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** Backoff is {@code 2^attempts} seconds with ±20% jitter, capped at 10 minutes (TECH §7). */
class OutboxBackoffTest {

    @Test
    void growsExponentiallyWithinTheJitterBand() {
        for (int attempts = 1; attempts <= 8; attempts++) {
            long base = (1L << attempts) * 1000;
            for (int i = 0; i < 50; i++) {
                assertThat(OutboxDispatcher.backoffMillis(attempts)).isBetween((long) (base * 0.8), (long) (base * 1.2));
            }
        }
    }

    @Test
    void isCappedAtTenMinutesNoMatterTheAttemptCount() {
        for (int attempts : new int[] {10, 11, 20, 100, Integer.MAX_VALUE}) {
            assertThat(OutboxDispatcher.backoffMillis(attempts)).isBetween(480_000L, 720_000L);
        }
    }
}
