package com.sopilot.core.outbox;

/**
 * Reacts to the end of an event's life. Both methods run in a transaction already bound to the
 * event's workspace, together with the outbox status update.
 */
public interface OutboxEventListener {

    /** ai-service accepted the event. */
    default void onDelivered(OutboxEvent event) {
    }

    /** The event will not be retried (contract error or too many attempts). */
    default void onDead(OutboxEvent event) {
    }
}
