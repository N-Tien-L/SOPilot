package com.poliwise.feedback.consumer;

import com.poliwise.feedback.config.RabbitMQConfig;
import com.poliwise.feedback.enums.AuditAction;
import com.poliwise.feedback.enums.ResourceType;
import com.poliwise.feedback.service.AuditLogService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;

@Component
public class ProfileEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(ProfileEventConsumer.class);

    private final AuditLogService auditLogService;

    public ProfileEventConsumer(AuditLogService auditLogService) {
        this.auditLogService = auditLogService;
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_USER_PROFILE)
    public void handleProfileUpdatedEvent(Map<String, Object> message) {
        try {
            UUID userId = parseUUID(message.get("userId"));
            String username = (String) message.get("username");
            UUID updatedBy = parseUUID(message.get("updatedBy"));
            String updatedByUsername = (String) message.get("updatedByUsername");
            @SuppressWarnings("unchecked")
            Map<String, Object> oldValues = (Map<String, Object>) message.get("oldValues");
            @SuppressWarnings("unchecked")
            Map<String, Object> newValues = (Map<String, Object>) message.get("newValues");
            Object changedFieldsRaw = message.get("changedFields");
            String[] changedFields = changedFieldsRaw instanceof String[]
                    ? (String[]) changedFieldsRaw
                    : changedFieldsRaw instanceof java.util.List
                            ? ((java.util.List<?>) changedFieldsRaw).toArray(new String[0])
                            : new String[0];

            Map<String, Object> metadata = Map.of(
                    "oldValues", oldValues != null ? oldValues : Map.of(),
                    "newValues", newValues != null ? newValues : Map.of(),
                    "changedFields", changedFields != null ? changedFields : new String[0]
            );

            String resourceName = username != null ? username : (userId != null ? userId.toString() : "unknown");
            String changedFieldsStr = changedFields != null && changedFields.length > 0
                    ? String.join(", ", changedFields)
                    : "unknown";

            auditLogService.logAction(userId, username, null,
                    AuditAction.USER_PROFILE_UPDATE, ResourceType.USER, userId,
                    resourceName, null, null, null, "feedback-service", metadata);

            log.info("Profile updated event processed: userId={}, updatedBy={}, changedFields=[{}]",
                    userId, updatedBy, changedFieldsStr);
        } catch (Exception e) {
            log.error("Failed to handle profile updated event", e);
        }
    }

    private UUID parseUUID(Object value) {
        if (value == null) return null;
        if (value instanceof UUID) return (UUID) value;
        try { return UUID.fromString(value.toString()); }
        catch (Exception e) { return null; }
    }
}
