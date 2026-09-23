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
public class LoginAuditConsumer {

    private static final Logger log = LoggerFactory.getLogger(LoginAuditConsumer.class);

    private final AuditLogService auditLogService;

    public LoginAuditConsumer(AuditLogService auditLogService) {
        this.auditLogService = auditLogService;
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_AUTH_LOGIN)
    public void handleLoginEvent(Map<String, Object> message) {
        try {
            String routingKey = (String) message.get("routingKey");
            if (routingKey == null) routingKey = "";

            UUID userId = parseUUID(message.get("userId"));
            String username = (String) message.get("username");
            String status = (String) message.get("status");
            String ipAddress = (String) message.get("ipAddress");

            AuditAction action;
            if (routingKey.contains("login.success") || "SUCCESS".equalsIgnoreCase(status)) {
                action = AuditAction.LOGIN_SUCCESS;
            } else if (routingKey.contains("logout") || "LOGOUT".equalsIgnoreCase(status)) {
                action = AuditAction.LOGOUT;
            } else {
                action = AuditAction.LOGIN_FAILED;
            }

            Map<String, Object> metadata = Map.of(
                    "loginStatus", status != null ? status : "UNKNOWN",
                    "failureReason", message.get("failureReason") != null ? message.get("failureReason") : ""
            );

            auditLogService.logAction(userId, username, null,
                    action, ResourceType.USER, userId,
                    username, ipAddress, null, null, "feedback-service", metadata);

            log.info("Login audit event processed: username={}, action={}, ip={}", username, action, ipAddress);
        } catch (Exception e) {
            log.error("Failed to handle login audit event", e);
        }
    }

    private UUID parseUUID(Object value) {
        if (value == null) return null;
        if (value instanceof UUID) return (UUID) value;
        try { return UUID.fromString(value.toString()); }
        catch (Exception e) { return null; }
    }
}
