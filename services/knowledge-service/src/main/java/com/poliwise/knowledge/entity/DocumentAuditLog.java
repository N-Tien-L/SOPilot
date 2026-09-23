package com.poliwise.knowledge.entity;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "document_audit_logs", schema = "knowledge")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocumentAuditLog {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "document_id")
    private UUID documentId;

    @Column(name = "action", nullable = false)
    private String action;

    @Column(name = "actor_id")
    private UUID actorId;

    @Column(name = "actor_username")
    private String actorUsername;

    @Type(JsonType.class)
    @Column(name = "old_values", columnDefinition = "jsonb")
    private Map<String, Object> oldValues;

    @Type(JsonType.class)
    @Column(name = "new_values", columnDefinition = "jsonb")
    private Map<String, Object> newValues;

    @Column(name = "ip_address")
    private String ipAddress;

    @Column(name = "user_agent", columnDefinition = "text")
    private String userAgent;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;
}
