package com.poliwise.feedback.controller;

import com.poliwise.feedback.enums.AuditAction;
import com.poliwise.feedback.enums.ResourceType;
import com.poliwise.feedback.service.AuditLogService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/internal")
public class AuditInternalController {

    private final AuditLogService auditLogService;

    public AuditInternalController(AuditLogService auditLogService) {
        this.auditLogService = auditLogService;
    }

    @PostMapping("/audit/user-created")
    public ResponseEntity<Void> logUserCreated(@RequestBody Map<String, Object> payload) {
        try {
            UUID actorId = payload.get("actorId") != null ? UUID.fromString(payload.get("actorId").toString()) : null;
            String actorName = (String) payload.getOrDefault("actorName", "System");
            UUID userId = payload.get("userId") != null ? UUID.fromString(payload.get("userId").toString()) : null;
            String username = (String) payload.get("username");
            String email = (String) payload.get("email");
            String role = (String) payload.get("role");

            auditLogService.logAction(actorId, actorName, null,
                    AuditAction.USER_CREATE, ResourceType.USER, userId,
                    username, null, null, null, "auth-service",
                    Map.of("email", email != null ? email : "",
                           "role", role != null ? role : ""));

            return ResponseEntity.ok().build();
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
}
