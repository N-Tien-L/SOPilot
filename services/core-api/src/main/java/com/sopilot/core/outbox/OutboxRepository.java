package com.sopilot.core.outbox;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * {@code core.outbox_events}. Inserts and status updates need the RLS context of the event's
 * workspace; {@link #claim} crosses workspaces through the {@code SECURITY DEFINER} function.
 */
@Repository
public class OutboxRepository {

    private final JdbcTemplate jdbc;

    public OutboxRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(UUID id, UUID workspaceId, UUID aggregateId, OutboxEvent.Type type, String payloadJson) {
        jdbc.update("INSERT INTO core.outbox_events (id, workspace_id, aggregate_id, event_type, payload) "
                + "VALUES (?, ?, ?, ?, ?::jsonb)", id, workspaceId, aggregateId, type.name(), payloadJson);
    }

    /**
     * Inserts an event that is already leased for 60 s, the same lease {@code claim_outbox_batch} takes: the
     * background dispatcher cannot claim it while its writer sends it directly (TECH §2.3), and picks it up
     * after the lease if the writer died.
     */
    public void insertLeased(UUID id, UUID workspaceId, UUID aggregateId, OutboxEvent.Type type, String payloadJson) {
        jdbc.update("INSERT INTO core.outbox_events (id, workspace_id, aggregate_id, event_type, payload, next_attempt_at) "
                + "VALUES (?, ?, ?, ?, ?::jsonb, now() + interval '60 seconds')",
                id, workspaceId, aggregateId, type.name(), payloadJson);
    }

    /** Leases up to {@code limit} due events of every workspace for 60 s (TECH §4.2). */
    public List<OutboxEvent> claim(int limit) {
        return jdbc.query("SELECT id, workspace_id, aggregate_id, event_type, payload::text, attempts "
                        + "FROM core.claim_outbox_batch(?)",
                (rs, i) -> new OutboxEvent(rs.getObject("id", UUID.class), rs.getObject("workspace_id", UUID.class),
                        rs.getObject("aggregate_id", UUID.class), OutboxEvent.Type.valueOf(rs.getString("event_type")),
                        rs.getString("payload"), rs.getInt("attempts")), limit);
    }

    public void markDelivered(UUID id) {
        jdbc.update("UPDATE core.outbox_events SET status = 'DELIVERED', delivered_at = now(), last_error = NULL, "
                + "attempts = attempts + 1 WHERE id = ?", id);
    }

    public void markRetry(UUID id, Instant nextAttemptAt, String error) {
        jdbc.update("UPDATE core.outbox_events SET attempts = attempts + 1, next_attempt_at = ?, last_error = ? "
                + "WHERE id = ?", java.sql.Timestamp.from(nextAttemptAt), error, id);
    }

    public void markDead(UUID id, String error) {
        jdbc.update("UPDATE core.outbox_events SET status = 'DEAD', attempts = attempts + 1, last_error = ? "
                + "WHERE id = ?", error, id);
    }

    /**
     * Updates the access object inside pending INGEST_REQUESTED events for a document (Race §7.1).
     */
    public int updatePendingIngestAccess(UUID workspaceId, UUID documentId, String accessJson) {
        return jdbc.update("UPDATE core.outbox_events SET payload = jsonb_set(payload, '{access}', ?::jsonb) "
                + "WHERE workspace_id = ? AND aggregate_id = ? AND event_type = 'INGEST_REQUESTED' AND status = 'PENDING'",
                accessJson, workspaceId, documentId);
    }
}
