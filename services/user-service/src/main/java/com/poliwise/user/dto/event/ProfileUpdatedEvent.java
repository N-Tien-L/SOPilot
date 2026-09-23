package com.poliwise.user.dto.event;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ProfileUpdatedEvent(
        UUID eventId,
        UUID userId,
        String username,
        UUID updatedBy,
        String updatedByUsername,
        Map<String, Object> oldValues,
        Map<String, Object> newValues,
        String[] changedFields,
        OffsetDateTime occurredAt
) {

    public static ProfileUpdatedEvent create(
            UUID userId, String username,
            UUID updatedBy, String updatedByUsername,
            Map<String, Object> oldValues,
            Map<String, Object> newValues,
            String[] changedFields) {
        return new ProfileUpdatedEvent(
                UUID.randomUUID(),
                userId, username,
                updatedBy, updatedByUsername,
                oldValues, newValues, changedFields,
                OffsetDateTime.now()
        );
    }
}
