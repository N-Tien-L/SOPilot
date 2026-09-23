package com.poliwise.metadata.entity;

import com.poliwise.metadata.enums.RulePermission;
import com.poliwise.metadata.enums.RuleTargetType;
import com.poliwise.metadata.enums.UserRole;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "document_access_rules", schema = "metadata")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocumentAccessRule {
    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "document_metadata_id", nullable = false)
    private UUID documentMetadataId;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "target_type", columnDefinition = "metadata.rule_target_type")
    private RuleTargetType targetType;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "target_role", columnDefinition = "core.user_role")
    private UserRole targetRole;

    @Column(name = "target_department_id")
    private UUID targetDepartmentId;

    @Column(name = "target_user_id")
    private UUID targetUserId;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "permission", columnDefinition = "metadata.rule_permission")
    private RulePermission permission;

    @Column(name = "created_by")
    private UUID createdBy;

    @Column(name = "created_at")
    private OffsetDateTime createdAt;

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public UUID getDocumentMetadataId() { return documentMetadataId; }
    public void setDocumentMetadataId(UUID documentMetadataId) { this.documentMetadataId = documentMetadataId; }
    public RuleTargetType getTargetType() { return targetType; }
    public void setTargetType(RuleTargetType targetType) { this.targetType = targetType; }
    public UserRole getTargetRole() { return targetRole; }
    public void setTargetRole(UserRole targetRole) { this.targetRole = targetRole; }
    public UUID getTargetDepartmentId() { return targetDepartmentId; }
    public void setTargetDepartmentId(UUID targetDepartmentId) { this.targetDepartmentId = targetDepartmentId; }
    public UUID getTargetUserId() { return targetUserId; }
    public void setTargetUserId(UUID targetUserId) { this.targetUserId = targetUserId; }
    public RulePermission getPermission() { return permission; }
    public void setPermission(RulePermission permission) { this.permission = permission; }
    public UUID getCreatedBy() { return createdBy; }
    public void setCreatedBy(UUID createdBy) { this.createdBy = createdBy; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime createdAt) { this.createdAt = createdAt; }
}
