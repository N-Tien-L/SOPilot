package com.sopilot.core.outbox;

import com.sopilot.core.config.OutboxProperties;
import com.sopilot.core.tenancy.TenantTx;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.time.Instant;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Sends outbox events to ai-service (TECH-V2-core-api §7). Two triggers: an immediate push on a
 * single worker thread right after the writing transaction commits, and a periodic poll that claims
 * due events with {@code FOR UPDATE SKIP LOCKED} (a 60 s lease, so a crashed sender is retried and two
 * dispatchers never send the same event at once). Retries back off as {@code 2^attempts} s capped at
 * 10 min with jitter; a 4xx other than 408/429 is a contract error and goes {@code DEAD} at once.
 */
@Component
public class OutboxDispatcher {

    private static final Logger log = LoggerFactory.getLogger(OutboxDispatcher.class);
    private static final int BATCH = 20;
    private static final long MAX_BACKOFF_SECONDS = 600;

    private final OutboxRepository outbox;
    private final AiServiceClient client;
    private final TenantTx tenant;
    private final OutboxProperties properties;
    private final List<OutboxEventListener> listeners;
    private final ExecutorService wake = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "outbox-wake");
        t.setDaemon(true);
        return t;
    });

    public OutboxDispatcher(OutboxRepository outbox, AiServiceClient client, TenantTx tenant,
                            OutboxProperties properties, List<OutboxEventListener> listeners) {
        this.outbox = outbox;
        this.client = client;
        this.tenant = tenant;
        this.properties = properties;
        this.listeners = listeners;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    void onEnqueued(OutboxService.Enqueued event) {
        if (properties.enabled()) {
            wake.submit(this::safeDispatch);
        }
    }

    @Scheduled(fixedDelayString = "${sopilot.outbox.poll:PT5S}")
    void poll() {
        if (properties.enabled()) {
            safeDispatch();
        }
    }

    @PreDestroy
    void shutdown() {
        wake.shutdownNow();
    }

    private void safeDispatch() {
        try {
            dispatchDue();
        } catch (RuntimeException e) {
            log.warn("Outbox dispatch failed: {}", e.getClass().getSimpleName());
        }
    }

    /** Sends every currently due event once; returns how many were claimed. */
    public synchronized int dispatchDue() {
        int total = 0;
        List<OutboxEvent> batch;
        while (!(batch = outbox.claim(BATCH)).isEmpty()) {
            total += batch.size();
            batch.forEach(this::deliver);
        }
        return total;
    }

    private void deliver(OutboxEvent event) {
        AiServiceClient.Result result = client.send(event);
        tenant.runVoid(event.workspaceId(), null, () -> {
            if (result.delivered()) {
                outbox.markDelivered(event.id());
                listeners.forEach(l -> l.onDelivered(event));
            } else if (result.retryable() && event.attempts() + 1 < properties.maxAttempts()) {
                outbox.markRetry(event.id(), Instant.now().plusMillis(backoffMillis(event.attempts() + 1)),
                        result.error());
            } else {
                outbox.markDead(event.id(), result.error());
                log.error("Outbox event {} ({}) is dead: {}", event.id(), event.type(), result.error());
                listeners.forEach(l -> l.onDead(event));
            }
        });
    }

    static long backoffMillis(int attempts) {
        long seconds = Math.min(1L << Math.min(attempts, 20), MAX_BACKOFF_SECONDS);
        return (long) (seconds * 1000 * ThreadLocalRandom.current().nextDouble(0.8, 1.2));
    }
}
