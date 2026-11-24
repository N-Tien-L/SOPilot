package com.sopilot.core.support;

import com.sopilot.core.outbox.AiServiceClient;
import com.sopilot.core.outbox.OutboxEvent;

import java.time.Duration;
import java.util.ArrayDeque;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.CopyOnWriteArrayList;

/** ai-service stand-in: records every event and answers with scripted statuses (202 by default). */
public class RecordingAiClient implements AiServiceClient {

    private final List<OutboxEvent> sent = new CopyOnWriteArrayList<>();
    private final List<Duration> timeouts = new CopyOnWriteArrayList<>();
    private final Queue<Result> script = new ArrayDeque<>();
    private volatile Result fallback = new Result(202, "HTTP 202");
    private volatile long delayMillis = 0;

    @Override
    public synchronized Result send(OutboxEvent event, Duration timeout) {
        sent.add(event);
        timeouts.add(timeout);
        if (delayMillis > 0) {
            try {
                // A response slower than the caller's timeout looks like a timeout to the caller.
                Thread.sleep(Math.min(delayMillis, timeout.toMillis()));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            if (delayMillis > timeout.toMillis()) {
                return new Result(-1, "HttpTimeoutException");
            }
        }
        Result next = script.poll();
        return next != null ? next : fallback;
    }

    public synchronized void respondWith(int... statuses) {
        for (int s : statuses) {
            script.add(new Result(s, s < 0 ? "ConnectException" : "HTTP " + s));
        }
    }

    public synchronized void alwaysRespondWith(int status) {
        fallback = new Result(status, status < 0 ? "ConnectException" : "HTTP " + status);
    }

    public synchronized void delayResponses(long millis) {
        this.delayMillis = millis;
    }

    public List<OutboxEvent> sent() {
        return sent;
    }

    /** The request timeout of every send, in order. */
    public List<Duration> timeouts() {
        return timeouts;
    }

    public long sentOfType(OutboxEvent.Type type) {
        return sent.stream().filter(e -> e.type() == type).count();
    }

    public synchronized void reset() {
        sent.clear();
        timeouts.clear();
        script.clear();
        fallback = new Result(202, "HTTP 202");
        delayMillis = 0;
    }
}

