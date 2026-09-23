package com.poliwise.metadata.service;

import com.poliwise.metadata.dto.*;
import com.poliwise.metadata.entity.DocumentAccessRule;
import com.poliwise.metadata.entity.DocumentMetadata;
import com.poliwise.metadata.enums.AccessLevel;
import com.poliwise.metadata.enums.DocumentStatus;
import com.poliwise.metadata.enums.RulePermission;
import com.poliwise.metadata.enums.RuleTargetType;
import com.poliwise.metadata.enums.UserRole;
import com.poliwise.metadata.exception.ResourceNotFoundException;
import com.poliwise.metadata.feign.UserServiceClient;
import com.poliwise.metadata.feign.dto.DepartmentDto;
import com.poliwise.metadata.feign.dto.UserDto;
import com.poliwise.metadata.feign.dto.UserPageResponse;
import com.poliwise.metadata.repository.DocumentAccessRuleRepository;
import com.poliwise.metadata.repository.DocumentMetadataRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class AccessRuleService {

    private static final Logger log = LoggerFactory.getLogger(AccessRuleService.class);

    private final DocumentAccessRuleRepository accessRuleRepository;
    private final DocumentMetadataRepository metadataRepository;
    private final UserServiceClient userServiceClient;

    public AccessRuleService(
            DocumentAccessRuleRepository accessRuleRepository,
            DocumentMetadataRepository metadataRepository,
            UserServiceClient userServiceClient) {
        this.accessRuleRepository = accessRuleRepository;
        this.metadataRepository = metadataRepository;
        this.userServiceClient = userServiceClient;
    }

    @Transactional
    public AccessRuleResponse create(UUID documentId, CreateAccessRuleRequest request, UUID createdBy) {
        UUID metadataId;

        if (documentId != null) {
            DocumentMetadata metadata = metadataRepository.findByDocumentIdAndDeletedAtIsNull(documentId)
                    .orElseGet(() -> {
                        log.info("No active metadata found for document {}, auto-creating metadata record", documentId);
                        OffsetDateTime now = OffsetDateTime.now();
                        DocumentMetadata newMetadata = DocumentMetadata.builder()
                                .id(UUID.randomUUID())
                                .documentId(documentId)
                                .title("Document " + documentId)
                                .accessLevel(AccessLevel.RESTRICTED)
                                .status(DocumentStatus.DRAFT)
                                .currentVersion(1)
                                .createdBy(createdBy)
                                .updatedBy(createdBy)
                                .createdAt(now)
                                .updatedAt(now)
                                .build();
                        return metadataRepository.save(newMetadata);
                    });
            metadataId = metadata.getId();
        } else if (request.documentMetadataId() != null) {
            if (!metadataRepository.existsById(request.documentMetadataId())) {
                throw new ResourceNotFoundException("Document metadata not found: " + request.documentMetadataId());
            }
            metadataId = request.documentMetadataId();
        } else {
            throw new IllegalArgumentException("Either documentId or documentMetadataId must be provided");
        }

        if (request.targetType() == null || request.targetType().isBlank()) {
            throw new IllegalArgumentException("Target type is required (ROLE, DEPARTMENT, USER)");
        }

        RuleTargetType targetType;
        try {
            targetType = RuleTargetType.valueOf(request.targetType().toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid target type: " + request.targetType() + ". Must be ROLE, DEPARTMENT, or USER");
        }

        RulePermission permission;
        try {
            permission = RulePermission.valueOf(request.permission().toUpperCase());
        } catch (IllegalArgumentException | NullPointerException e) {
            throw new IllegalArgumentException("Invalid permission: " + request.permission() + ". Must be VIEW or DENY");
        }

        switch (targetType) {
            case ROLE -> {
                if (request.targetRole() == null) {
                    throw new IllegalArgumentException("Role must be specified for ROLE target type");
                }
            }
            case DEPARTMENT -> {
                if (request.targetDepartmentId() == null) {
                    throw new IllegalArgumentException("Department ID must be specified for DEPARTMENT target type");
                }
            }
            case USER -> {
                if (request.targetUserId() == null) {
                    throw new IllegalArgumentException("User ID must be specified for USER target type");
                }
            }
        }

        OffsetDateTime now = OffsetDateTime.now();
        DocumentAccessRule rule = DocumentAccessRule.builder()
                .id(UUID.randomUUID())
                .documentMetadataId(metadataId)
                .targetType(targetType)
                .targetRole(request.targetRole() != null ? UserRole.valueOf(request.targetRole().toUpperCase()) : null)
                .targetDepartmentId(request.targetDepartmentId())
                .targetUserId(request.targetUserId())
                .permission(permission)
                .createdBy(createdBy)
                .createdAt(now)
                .build();

        DocumentAccessRule saved = accessRuleRepository.save(rule);
        log.info("Created access rule: id={}, documentId={}, metadataId={}, targetType={}, permission={}",
                saved.getId(), documentId, metadataId, saved.getTargetType(), saved.getPermission());
        return toResponse(saved);
    }

    @Transactional
    public AccessRuleResponse update(UUID ruleId, UpdateAccessRuleRequest request, UUID updatedBy) {
        DocumentAccessRule rule = accessRuleRepository.findById(ruleId)
                .orElseThrow(() -> new ResourceNotFoundException("Access rule not found: " + ruleId));

        if (request.targetType() == null || request.targetType().isBlank()) {
            throw new IllegalArgumentException("Target type is required");
        }

        RuleTargetType targetType;
        try {
            targetType = RuleTargetType.valueOf(request.targetType().toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid target type: " + request.targetType());
        }

        RulePermission permission;
        try {
            permission = RulePermission.valueOf(request.permission().toUpperCase());
        } catch (IllegalArgumentException | NullPointerException e) {
            throw new IllegalArgumentException("Invalid permission: " + request.permission());
        }

        switch (targetType) {
            case ROLE -> {
                if (request.targetRole() == null) {
                    throw new IllegalArgumentException("Role must be specified for ROLE target type");
                }
            }
            case DEPARTMENT -> {
                if (request.targetDepartmentId() == null) {
                    throw new IllegalArgumentException("Department ID must be specified for DEPARTMENT target type");
                }
            }
            case USER -> {
                if (request.targetUserId() == null) {
                    throw new IllegalArgumentException("User ID must be specified for USER target type");
                }
            }
        }

        rule.setTargetType(targetType);
        rule.setTargetRole(request.targetRole() != null ? UserRole.valueOf(request.targetRole().toUpperCase()) : null);
        rule.setTargetDepartmentId(request.targetDepartmentId());
        rule.setTargetUserId(request.targetUserId());
        rule.setPermission(permission);

        DocumentAccessRule saved = accessRuleRepository.save(rule);
        log.info("Updated access rule: id={}, targetType={}, permission={}", saved.getId(), saved.getTargetType(), saved.getPermission());
        return toResponse(saved);
    }

    public List<AccessRuleResponse> getByMetadataId(UUID metadataId) {
        return accessRuleRepository.findByDocumentMetadataId(metadataId)
                .stream()
                .map(this::toResponse)
                .toList();
    }

    public List<AccessRuleResponse> getByDocumentId(UUID documentId) {
        return metadataRepository.findByDocumentIdAndDeletedAtIsNull(documentId)
                .map(metadata -> {
                    log.info("Found metadata for document {}: metadataId={}", documentId, metadata.getId());
                    List<AccessRuleResponse> rules = accessRuleRepository.findByDocumentMetadataId(metadata.getId())
                            .stream()
                            .map(this::toResponse)
                            .toList();
                    log.info("Found {} access rules for metadataId={}", rules.size(), metadata.getId());
                    return rules;
                })
                .orElseGet(() -> {
                    log.warn("No active metadata found for documentId={} — access rules cannot be loaded", documentId);
                    return List.of();
                });
    }

    public List<AccessRuleResponse> getAll() {
        return accessRuleRepository.findAll()
                .stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public void delete(UUID id) {
        if (!accessRuleRepository.existsById(id)) {
            throw new ResourceNotFoundException("Access rule not found: " + id);
        }
        accessRuleRepository.deleteById(id);
        log.info("Deleted access rule: id={}", id);
    }

    @Transactional
    public void deleteByMetadataId(UUID metadataId) {
        List<DocumentAccessRule> rules = accessRuleRepository.findByDocumentMetadataId(metadataId);
        accessRuleRepository.deleteAll(rules);
        log.info("Deleted {} access rules for metadata: {}", rules.size(), metadataId);
    }

    public boolean hasAccess(UUID metadataId, UUID userId, UserRole role, UUID departmentId) {
        if (role == UserRole.ADMIN) {
            log.debug("Admin always has access: metadataId={}", metadataId);
            return true;
        }

        DocumentMetadata metadata = metadataRepository.findByIdAndDeletedAtIsNull(metadataId).orElse(null);
        if (metadata == null) {
            log.warn("Document metadata not found: {}", metadataId);
            return false;
        }

        if (metadata.getAccessLevel() != null &&
            metadata.getAccessLevel() == AccessLevel.PUBLIC) {
            log.debug("Public document: metadataId={}", metadataId);
            return true;
        }

        List<DocumentAccessRule> rules = accessRuleRepository.findByDocumentMetadataId(metadataId);

        if (rules.isEmpty()) {
            log.debug("No access rules, denying: metadataId={}", metadataId);
            return false;
        }

        boolean hasExplicitDeny = checkDenyRules(rules, userId, role, departmentId);
        if (hasExplicitDeny) {
            log.debug("User explicitly denied: metadataId={}, userId={}", metadataId, userId);
            return false;
        }

        boolean hasViewAccess = checkViewRules(rules, userId, role, departmentId);
        if (hasViewAccess) {
            log.debug("User granted view access: metadataId={}, userId={}", metadataId, userId);
            return true;
        }

        log.debug("No matching rules, denying: metadataId={}, userId={}", metadataId, userId);
        return false;
    }

    private boolean checkDenyRules(List<DocumentAccessRule> rules, UUID userId, UserRole role, UUID departmentId) {
        for (DocumentAccessRule rule : rules) {
            if (rule.getPermission() != RulePermission.DENY) {
                continue;
            }
            if (matchesRule(rule, userId, role, departmentId)) {
                return true;
            }
        }
        return false;
    }

    private boolean checkViewRules(List<DocumentAccessRule> rules, UUID userId, UserRole role, UUID departmentId) {
        for (DocumentAccessRule rule : rules) {
            if (rule.getPermission() != RulePermission.VIEW) {
                continue;
            }
            if (matchesRule(rule, userId, role, departmentId)) {
                return true;
            }
        }
        return false;
    }

    private boolean matchesRule(DocumentAccessRule rule, UUID userId, UserRole role, UUID departmentId) {
        switch (rule.getTargetType()) {
            case USER -> {
                return rule.getTargetUserId() != null && rule.getTargetUserId().equals(userId);
            }
            case DEPARTMENT -> {
                return rule.getTargetDepartmentId() != null &&
                       departmentId != null &&
                       rule.getTargetDepartmentId().equals(departmentId);
            }
            case ROLE -> {
                return rule.getTargetRole() != null && rule.getTargetRole() == role;
            }
            default -> {
                log.warn("Unknown target type in rule {}: {}", rule.getId(), rule.getTargetType());
                return false;
            }
        }
    }

    public List<UUID> filterAccessibleDocuments(List<UUID> metadataIds, UUID userId, UserRole role, UUID departmentId) {
        return metadataIds.stream()
                .filter(id -> hasAccess(id, userId, role, departmentId))
                .toList();
    }

    public FilterAccessibleDocumentsResponse filterAccessibleDocumentsBatch(
            List<UUID> documentIds,
            UUID userId,
            String roleStr,
            UUID departmentId) {

        UserRole role = null;
        if (roleStr != null && !roleStr.isBlank()) {
            try {
                role = UserRole.valueOf(roleStr.toUpperCase());
            } catch (IllegalArgumentException e) {
                log.warn("Invalid role in filter request: {}", roleStr);
                return new FilterAccessibleDocumentsResponse(List.of(), documentIds.size(), 0);
            }
        }

        // Convert documentIds to metadataIds via metadataRepository
        List<UUID> metadataIds = documentIds.stream()
                .map(docId -> metadataRepository.findByDocumentIdAndDeletedAtIsNull(docId)
                        .map(DocumentMetadata::getId)
                        .orElse(null))
                .filter(id -> id != null)
                .toList();

        List<UUID> accessibleMetadataIds = filterAccessibleDocuments(metadataIds, userId, role, departmentId);

        // Convert metadataIds back to documentIds
        List<UUID> accessibleDocumentIds = accessibleMetadataIds.stream()
                .map(metaId -> metadataRepository.findById(metaId)
                        .map(DocumentMetadata::getDocumentId)
                        .orElse(null))
                .filter(id -> id != null)
                .toList();

        log.info("Filtered {} documents for user {}: {} accessible out of {} requested",
                documentIds.size(), userId, accessibleDocumentIds.size(), documentIds.size());

        return new FilterAccessibleDocumentsResponse(accessibleDocumentIds, documentIds.size(), accessibleDocumentIds.size());
    }

    public DocumentAccessCheckResponse checkDocumentAccess(UUID documentId, UUID userId, String roleStr, UUID departmentId) {
        UUID metadataId = metadataRepository.findByDocumentIdAndDeletedAtIsNull(documentId)
                .map(DocumentMetadata::getId)
                .orElse(null);

        if (metadataId == null) {
            log.warn("Document metadata not found for documentId={}", documentId);
            return new DocumentAccessCheckResponse(documentId, false, "Tài liệu không tồn tại");
        }

        UserRole role = null;
        if (roleStr != null && !roleStr.isBlank()) {
            try {
                role = UserRole.valueOf(roleStr.toUpperCase());
            } catch (IllegalArgumentException e) {
                return new DocumentAccessCheckResponse(documentId, false, "Vai trò không hợp lệ");
            }
        }

        boolean hasAccess = hasAccess(metadataId, userId, role, departmentId);
        String reason = hasAccess ? "Có quyền truy cập" : "Không có quyền truy cập";

        return new DocumentAccessCheckResponse(documentId, hasAccess, reason);
    }

    public AccessRuleSimulationResult simulateAccess(UUID documentId) {
        UUID metadataId = metadataRepository.findByDocumentIdAndDeletedAtIsNull(documentId)
                .map(DocumentMetadata::getId)
                .orElseThrow(() -> new ResourceNotFoundException("No active metadata found for document: " + documentId));

        List<DocumentAccessRule> rules = accessRuleRepository.findByDocumentMetadataId(metadataId);
        List<DepartmentDto> departments = fetchActiveDepartments();
        Map<UUID, DepartmentDto> deptMap = departments.stream()
                .collect(java.util.stream.Collectors.toMap(DepartmentDto::id, d -> d, (a, b) -> a));
        List<UserDto> allUsers = fetchAllActiveUsers();

        List<AccessRuleSimulationResponse> grantedUsers = new ArrayList<>();
        List<AccessRuleSimulationResponse> deniedUsers = new ArrayList<>();

        for (UserDto user : allUsers) {
            DepartmentDto userDept = user.departmentId() != null ? deptMap.get(user.departmentId()) : null;
            boolean hasAccess = simulateUserAccess(rules, user, userDept);
            AccessRuleSimulationResponse simResponse = buildSimulationResponse(user, userDept, hasAccess);
            if (hasAccess) {
                grantedUsers.add(simResponse);
            } else {
                deniedUsers.add(simResponse);
            }
        }

        log.info("Simulation complete for document {}: totalUsers={}, granted={}, denied={}",
                documentId, allUsers.size(), grantedUsers.size(), deniedUsers.size());

        return new AccessRuleSimulationResult(
                documentId,
                metadataId,
                allUsers.size(),
                grantedUsers.size(),
                deniedUsers.size(),
                grantedUsers,
                deniedUsers,
                OffsetDateTime.now()
        );
    }

    private boolean simulateUserAccess(List<DocumentAccessRule> rules, UserDto user, DepartmentDto dept) {
        if (user.role() == null) return false;

        UserRole userRole;
        try {
            userRole = UserRole.valueOf(user.role().toUpperCase());
        } catch (IllegalArgumentException e) {
            return false;
        }

        if (userRole == UserRole.ADMIN) return true;

        if (rules.isEmpty()) return false;

        UUID userDeptId = dept != null ? dept.id() : null;

        boolean hasExplicitDeny = false;
        boolean hasViewAccess = false;

        for (DocumentAccessRule rule : rules) {
            if (rule.getPermission() != RulePermission.DENY) continue;
            if (matchesSimulationRule(rule, user.id(), userRole, userDeptId)) {
                hasExplicitDeny = true;
                break;
            }
        }

        if (!hasExplicitDeny) {
            for (DocumentAccessRule rule : rules) {
                if (rule.getPermission() != RulePermission.VIEW) continue;
                if (matchesSimulationRule(rule, user.id(), userRole, userDeptId)) {
                    hasViewAccess = true;
                    break;
                }
            }
        }

        return hasViewAccess && !hasExplicitDeny;
    }

    private boolean matchesSimulationRule(DocumentAccessRule rule, UUID userId, UserRole role, UUID departmentId) {
        switch (rule.getTargetType()) {
            case USER -> {
                return rule.getTargetUserId() != null && rule.getTargetUserId().equals(userId);
            }
            case DEPARTMENT -> {
                return rule.getTargetDepartmentId() != null &&
                       departmentId != null &&
                       rule.getTargetDepartmentId().equals(departmentId);
            }
            case ROLE -> {
                return rule.getTargetRole() != null && rule.getTargetRole() == role;
            }
            default -> {
                return false;
            }
        }
    }

    private AccessRuleSimulationResponse buildSimulationResponse(UserDto user, DepartmentDto dept, boolean hasAccess) {
        String reason;
        if (user.role() != null && user.role().equalsIgnoreCase("ADMIN")) {
            reason = "Quyền ADMIN — luôn được phép truy cập";
        } else if (hasAccess) {
            reason = "Có quyền truy cập (phù hợp với quy tắc VIEW)";
        } else {
            reason = "Không có quyền truy cập";
        }

        return new AccessRuleSimulationResponse(
                user.id(),
                user.username(),
                user.fullName(),
                user.role(),
                dept != null ? dept.id() : null,
                dept != null ? dept.name() : null,
                hasAccess,
                reason,
                OffsetDateTime.now()
        );
    }

    private List<DepartmentDto> fetchActiveDepartments() {
        try {
            return userServiceClient.getActiveDepartments();
        } catch (Exception e) {
            log.warn("Failed to fetch active departments from user-service: {}", e.getMessage());
            return List.of();
        }
    }

    private List<UserDto> fetchAllActiveUsers() {
        try {
            UserPageResponse response = userServiceClient.searchUsers(0, 10000, "ACTIVE");
            return response.content();
        } catch (Exception e) {
            log.warn("Failed to fetch active users from user-service: {}", e.getMessage());
            return List.of();
        }
    }

    private AccessRuleResponse toResponse(DocumentAccessRule rule) {
        String departmentName = null;
        String userName = null;

        if (rule.getTargetDepartmentId() != null) {
            try {
                DepartmentDto dept = userServiceClient.getDepartmentById(rule.getTargetDepartmentId());
                if (dept != null) {
                    departmentName = dept.name();
                }
            } catch (Exception e) {
                log.debug("Could not resolve department name for id={}: {}", rule.getTargetDepartmentId(), e.getMessage());
            }
        }

        if (rule.getTargetUserId() != null) {
            try {
                UserDto usr = userServiceClient.getUserById(rule.getTargetUserId());
                if (usr != null) {
                    userName = usr.fullName() != null ? usr.fullName() : usr.username();
                }
            } catch (Exception e) {
                log.debug("Could not resolve user name for id={}: {}", rule.getTargetUserId(), e.getMessage());
            }
        }

        return new AccessRuleResponse(
                rule.getId(),
                rule.getDocumentMetadataId(),
                rule.getTargetType() != null ? rule.getTargetType().name() : null,
                rule.getTargetRole() != null ? rule.getTargetRole().name() : null,
                rule.getTargetDepartmentId(),
                departmentName,
                rule.getTargetUserId(),
                userName,
                rule.getPermission() != null ? rule.getPermission().name() : null,
                rule.getCreatedBy(),
                rule.getCreatedAt()
        );
    }
}
