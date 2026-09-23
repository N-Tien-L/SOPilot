package com.poliwise.feedback.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.poliwise.feedback.dto.request.AuditLogSearchRequest;
import com.poliwise.feedback.dto.response.AuditLogResponse;
import com.poliwise.feedback.entity.AuditLog;
import com.poliwise.feedback.enums.AuditAction;
import com.poliwise.feedback.enums.ResourceType;
import com.poliwise.feedback.repository.AuditLogRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;

@Service
@Transactional
public class AuditLogService {

    private static final Logger log = LoggerFactory.getLogger(AuditLogService.class);
    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper;

    @Value("${poliwise.cleanup.audit-retention-days:90}")
    private int auditRetentionDays;

    public AuditLogService(AuditLogRepository auditLogRepository, ObjectMapper objectMapper) {
        this.auditLogRepository = auditLogRepository;
        this.objectMapper = objectMapper;
    }

    public void logAction(UUID userId, String username, String userRole,
                          AuditAction action, ResourceType resourceType, UUID resourceId,
                          String resourceName, String ipAddress, String userAgent,
                          String traceId, String serviceName, Map<String, Object> metadata) {
        try {
            AuditLog auditLog = AuditLog.builder()
                    .userId(userId).username(username).userRole(userRole)
                    .action(action).resourceType(resourceType).resourceId(resourceId)
                    .resourceName(resourceName).ipAddress(ipAddress).userAgent(userAgent)
                    .traceId(traceId).serviceName(serviceName)
                    .metadata(metadata != null ? objectMapper.writeValueAsString(metadata) : null)
                    .build();
            auditLogRepository.save(auditLog);
        } catch (Exception e) {
            log.error("Failed to log audit action: {}", action, e);
        }
    }

    @Transactional(readOnly = true)
    public Page<AuditLogResponse> searchLogs(AuditLogSearchRequest request, Pageable pageable) {
        Page<AuditLog> logs;
        if (request.resourceType() != null && request.resourceId() != null) {
            logs = auditLogRepository.findByResourceTypeAndResourceId(request.resourceType(), request.resourceId(), pageable);
        } else if (request.action() != null) {
            logs = auditLogRepository.findByAction(request.action(), pageable);
        } else if (request.userId() != null) {
            logs = auditLogRepository.findByUserId(request.userId(), pageable);
        } else if (request.fromDate() != null && request.toDate() != null) {
            Instant from = request.fromDate().toInstant(ZoneOffset.UTC);
            Instant to = request.toDate().toInstant(ZoneOffset.UTC);
            logs = auditLogRepository.findByCreatedAtBetween(from, to, pageable);
        } else if (request.search() != null && !request.search().isBlank()) {
            logs = auditLogRepository.findByUsernameContainingIgnoreCase(request.search(), pageable);
        } else {
            logs = auditLogRepository.findAll(pageable);
        }
        return logs.map(this::toResponse);
    }

    @Transactional(readOnly = true)
    public AuditLogResponse getAuditLogById(UUID id) {
        return auditLogRepository.findById(id).map(this::toResponse).orElse(null);
    }

    public long cleanupOldLogs() {
        Instant cutoff = Instant.now().minusSeconds((long) auditRetentionDays * 24 * 60 * 60);
        long count = auditLogRepository.countByCreatedAtBefore(cutoff);
        auditLogRepository.deleteByCreatedAtBefore(cutoff);
        log.info("Cleaned up {} old audit logs older than {} days", count, auditRetentionDays);
        return count;
    }

    private AuditLogResponse toResponse(AuditLog auditLog) {
        Map<String, Object> oldValue = null;
        Map<String, Object> newValue = null;
        String[] changedFieldsArr = new String[0];
        if (auditLog.getMetadata() != null) {
            try {
                @SuppressWarnings("unchecked")
                Map<String, Object> meta = objectMapper.readValue(auditLog.getMetadata(), Map.class);
                Object ov = meta.get("oldValues");
                if (ov instanceof Map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> ovm = (Map<String, Object>) ov;
                    oldValue = ovm;
                }
                Object nv = meta.get("newValues");
                if (nv instanceof Map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> nvm = (Map<String, Object>) nv;
                    newValue = nvm;
                }
                Object cf = meta.get("changedFields");
                if (cf instanceof String[]) {
                    changedFieldsArr = (String[]) cf;
                } else if (cf instanceof java.util.List) {
                    java.util.List<?> cfl = (java.util.List<?>) cf;
                    changedFieldsArr = cfl.toArray(new String[0]);
                }
            } catch (Exception e) {
                log.warn("Failed to parse audit log metadata for id={}", auditLog.getId(), e);
            }
        }
        return new AuditLogResponse(auditLog.getId(), auditLog.getUserId(), auditLog.getUsername(),
                auditLog.getUserRole(), auditLog.getAction(), auditLog.getResourceType(),
                auditLog.getResourceId(), auditLog.getResourceName(), auditLog.getIpAddress(), auditLog.getCreatedAt(),
                oldValue, newValue, changedFieldsArr);
    }
}
