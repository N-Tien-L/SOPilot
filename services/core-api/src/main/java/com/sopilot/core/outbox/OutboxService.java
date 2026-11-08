package com.sopilot.core.outbox;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.common.UuidV7;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.UUID;

/**
 * Writes an outbox row in the caller's transaction (so it commits with the change it announces) and
 * announces it for an immediate push after commit (TECH §7). Callers must have bound the RLS context.
 */
@Service
public class OutboxService {

    /** Published inside the transaction; the dispatcher acts on it only after commit. */
    public record Enqueued(UUID id) {
    }

    private final OutboxRepository outbox;
    private final ObjectMapper mapper;
    private final ApplicationEventPublisher events;

    public OutboxService(OutboxRepository outbox, ObjectMapper mapper, ApplicationEventPublisher events) {
        this.outbox = outbox;
        this.mapper = mapper;
        this.events = events;
    }

    public UUID enqueue(UUID workspaceId, UUID documentId, OutboxEvent.Type type, Map<String, Object> payload) {
        UUID id = UuidV7.generate();
        try {
            outbox.insert(id, workspaceId, documentId, type, mapper.writeValueAsString(payload));
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Outbox payload is not serializable");
        }
        events.publishEvent(new Enqueued(id));
        return id;
    }
}
