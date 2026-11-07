package com.sopilot.core.support;

import com.sopilot.core.outbox.AiServiceClient;
import com.sopilot.core.outbox.OutboxEvent;

import java.util.ArrayDeque;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.CopyOnWriteArrayList;

/** ai-service stand-in: records every event and answers with scripted statuses (202 by default). */
public class RecordingAiClient implements AiServiceClient {

    private final List<OutboxEvent> sent = new CopyOnWriteArrayList<>();
    private final Queue<Result> script = new ArrayDeque<>();
    private volatile Result fallback = new Result(202, "HTTP 202");

    @Override
    public synchronized Result send(OutboxEvent event) {
        sent.add(event);
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

    public List<OutboxEvent> sent() {
        return sent;
    }

    public long sentOfType(OutboxEvent.Type type) {
        return sent.stream().filter(e -> e.type() == type).count();
    }

    public synchronized void reset() {
        sent.clear();
        script.clear();
        fallback = new Result(202, "HTTP 202");
    }
}
