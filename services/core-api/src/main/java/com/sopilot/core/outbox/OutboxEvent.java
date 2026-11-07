package com.sopilot.core.outbox;

import java.util.UUID;

/** One {@code core.outbox_events} row; {@code payload} is the JSON text sent to ai-service. */
public record OutboxEvent(UUID id, UUID workspaceId, UUID aggregateId, Type type, String payload, int attempts) {

    public enum Type { INGEST_REQUESTED, ACCESS_UPDATED, DOCUMENT_DELETED }
}
