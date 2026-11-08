package com.sopilot.core.document;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.document.DocumentRepository.VersionRow;
import com.sopilot.core.outbox.OutboxEvent;
import com.sopilot.core.outbox.OutboxEventListener;
import com.sopilot.core.storage.StorageClient;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.UUID;

/**
 * Document side effects of the end of an outbox event (TECH §3.3, §7). Runs inside the dispatcher's
 * tenant transaction.
 * <ul>
 *   <li>{@code DOCUMENT_DELETED} delivered: ai-service removed its chunks, so the files and rows go too.</li>
 *   <li>{@code INGEST_REQUESTED} dead: the version becomes {@code FAILED/DISPATCH_FAILED} so the user can retry.</li>
 * </ul>
 */
@Component
public class DocumentOutboxHooks implements OutboxEventListener {

    private final DocumentRepository docs;
    private final StorageClient storage;
    private final ObjectMapper mapper;

    public DocumentOutboxHooks(DocumentRepository docs, StorageClient storage, ObjectMapper mapper) {
        this.docs = docs;
        this.storage = storage;
        this.mapper = mapper;
    }

    @Override
    public void onDelivered(OutboxEvent event) {
        if (event.type() != OutboxEvent.Type.DOCUMENT_DELETED) {
            return;
        }
        List<String> keys = docs.objectKeys(event.workspaceId(), event.aggregateId());
        docs.hardDelete(event.workspaceId(), event.aggregateId());
        // Keys that survive a failed delete are orphans, which StorageJanitor removes.
        AfterCommit.run("delete document objects", () -> keys.forEach(storage::delete));
    }

    @Override
    public void onDead(OutboxEvent event) {
        if (event.type() != OutboxEvent.Type.INGEST_REQUESTED) {
            return;
        }
        try {
            JsonNode payload = mapper.readTree(event.payload());
            UUID versionId = UUID.fromString(payload.get("versionId").asText());
            int attempt = payload.path("attempt").asInt(0);
            docs.findVersionForUpdate(event.workspaceId(), event.aggregateId(), versionId)
                    .filter(v -> "UPLOADED".equals(v.status()) && v.attempt() == attempt)
                    .map(VersionRow::id)
                    .ifPresent(id -> docs.markFailed(id, "DISPATCH_FAILED", FailureMessages.forCode("DISPATCH_FAILED")));
        } catch (java.io.IOException | RuntimeException e) {
            throw new IllegalStateException("Outbox payload could not be read");
        }
    }
}
