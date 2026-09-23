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
public class DepartmentEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(DepartmentEventConsumer.class);

    private final AuditLogService auditLogService;

    public DepartmentEventConsumer(AuditLogService auditLogService) {
        this.auditLogService = auditLogService;
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_DEPT_CREATED)
    public void handleDepartmentCreated(Map<String, Object> message) {
        try {
            UUID actorId = parseUUID(message.get("createdBy"));
            String actorName = actorId != null ? "Admin" : "System";
            UUID deptId = parseUUID(message.get("departmentId"));
            String deptName = (String) message.get("departmentName");
            String deptCode = (String) message.get("departmentCode");
            UUID parentId = parseUUID(message.get("parentId"));

            auditLogService.logAction(actorId, actorName, null,
                    AuditAction.DEPARTMENT_CREATE, ResourceType.DEPARTMENT, deptId,
                    deptName, null, null, null, "feedback-service",
                    Map.of("departmentId", deptId != null ? deptId.toString() : "",
                           "departmentName", deptName != null ? deptName : "",
                           "departmentCode", deptCode != null ? deptCode : "",
                           "parentId", parentId != null ? parentId.toString() : ""));

            log.info("Department created event processed: deptId={}, name={}", deptId, deptName);
        } catch (Exception e) {
            log.error("Failed to handle department created event", e);
        }
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_DEPT_UPDATED)
    public void handleDepartmentUpdated(Map<String, Object> message) {
        try {
            UUID actorId = parseUUID(message.get("updatedBy"));
            String actorName = actorId != null ? "Admin" : "System";
            UUID deptId = parseUUID(message.get("departmentId"));
            String deptName = (String) message.get("departmentName");
            String deptCode = (String) message.get("departmentCode");

            auditLogService.logAction(actorId, actorName, null,
                    AuditAction.DEPARTMENT_UPDATE, ResourceType.DEPARTMENT, deptId,
                    deptName, null, null, null, "feedback-service",
                    Map.of("departmentId", deptId != null ? deptId.toString() : "",
                           "departmentName", deptName != null ? deptName : "",
                           "departmentCode", deptCode != null ? deptCode : ""));

            log.info("Department updated event processed: deptId={}, name={}", deptId, deptName);
        } catch (Exception e) {
            log.error("Failed to handle department updated event", e);
        }
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_DEPT_DELETED)
    public void handleDepartmentDeleted(Map<String, Object> message) {
        try {
            UUID actorId = parseUUID(message.get("deletedBy"));
            String actorName = actorId != null ? "Admin" : "System";
            UUID deptId = parseUUID(message.get("departmentId"));
            String deptName = (String) message.get("departmentName");
            String deptCode = (String) message.get("departmentCode");

            auditLogService.logAction(actorId, actorName, null,
                    AuditAction.DEPARTMENT_DELETE, ResourceType.DEPARTMENT, deptId,
                    deptName, null, null, null, "feedback-service",
                    Map.of("departmentId", deptId != null ? deptId.toString() : "",
                           "departmentName", deptName != null ? deptName : "",
                           "departmentCode", deptCode != null ? deptCode : ""));

            log.info("Department deleted event processed: deptId={}, name={}", deptId, deptName);
        } catch (Exception e) {
            log.error("Failed to handle department deleted event", e);
        }
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_USER_ASSIGNED_DEPT)
    public void handleUserAssignedToDepartment(Map<String, Object> message) {
        try {
            UUID actorId = parseUUID(message.get("assignedBy"));
            String actorName = actorId != null ? "Admin" : "System";
            UUID userId = parseUUID(message.get("userId"));
            String username = (String) message.get("username");
            UUID deptId = parseUUID(message.get("departmentId"));
            String deptName = (String) message.get("departmentName");

            auditLogService.logAction(actorId, actorName, null,
                    AuditAction.USER_UPDATE, ResourceType.USER, userId,
                    username, null, null, null, "feedback-service",
                    Map.of("action", "assigned_to_department",
                           "departmentId", deptId != null ? deptId.toString() : "",
                           "departmentName", deptName != null ? deptName : ""));

            log.info("User assigned to department event processed: userId={}, deptId={}", userId, deptId);
        } catch (Exception e) {
            log.error("Failed to handle user assigned to department event", e);
        }
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_USER_REMOVED_DEPT)
    public void handleUserRemovedFromDepartment(Map<String, Object> message) {
        try {
            UUID actorId = parseUUID(message.get("removedBy"));
            String actorName = actorId != null ? "Admin" : "System";
            UUID userId = parseUUID(message.get("userId"));
            String username = (String) message.get("username");
            UUID deptId = parseUUID(message.get("departmentId"));
            String deptName = (String) message.get("departmentName");

            auditLogService.logAction(actorId, actorName, null,
                    AuditAction.USER_UPDATE, ResourceType.USER, userId,
                    username, null, null, null, "feedback-service",
                    Map.of("action", "removed_from_department",
                           "departmentId", deptId != null ? deptId.toString() : "",
                           "departmentName", deptName != null ? deptName : ""));

            log.info("User removed from department event processed: userId={}, deptId={}", userId, deptId);
        } catch (Exception e) {
            log.error("Failed to handle user removed from department event", e);
        }
    }

    private UUID parseUUID(Object value) {
        if (value == null) return null;
        if (value instanceof UUID) return (UUID) value;
        try { return UUID.fromString(value.toString()); }
        catch (Exception e) { return null; }
    }
}
