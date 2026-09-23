package com.poliwise.metadata.repository;

import com.poliwise.metadata.entity.DocumentAccessRule;
import com.poliwise.metadata.enums.RulePermission;
import com.poliwise.metadata.enums.RuleTargetType;
import com.poliwise.metadata.enums.UserRole;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

@Repository
public interface DocumentAccessRuleRepository extends JpaRepository<DocumentAccessRule, UUID>,
                JpaSpecificationExecutor<DocumentAccessRule> {

        List<DocumentAccessRule> findByDocumentMetadataId(UUID documentMetadataId);

        List<DocumentAccessRule> findByDocumentMetadataIdAndTargetType(UUID documentMetadataId,
                        RuleTargetType targetType);

        List<DocumentAccessRule> findByDocumentMetadataIdAndTargetDepartmentId(
                        UUID documentMetadataId, UUID targetDepartmentId);

        List<DocumentAccessRule> findByDocumentMetadataIdAndTargetUserId(UUID documentMetadataId,
                        UUID targetUserId);

        long deleteByDocumentMetadataId(UUID documentMetadataId);

        boolean existsByDocumentMetadataIdAndTargetTypeAndTargetRole(
                        UUID documentMetadataId, RuleTargetType targetType, UserRole targetRole);

        boolean existsByDocumentMetadataIdAndTargetTypeAndTargetDepartmentId(
                        UUID documentMetadataId, RuleTargetType targetType, UUID targetDepartmentId);

        boolean existsByDocumentMetadataIdAndTargetTypeAndTargetUserId(
                        UUID documentMetadataId, RuleTargetType targetType, UUID targetUserId);
}
