package com.poliwise.metadata.service;

import com.poliwise.metadata.dto.CreateDocumentMetadataRequest;
import com.poliwise.metadata.dto.UpdateDocumentMetadataRequest;
import com.poliwise.metadata.dto.DocumentMetadataResponse;
import com.poliwise.metadata.dto.DocumentAccessCheckResponse;
import com.poliwise.metadata.dto.TagResponse;
import com.poliwise.metadata.dto.AccessRuleResponse;
import com.poliwise.metadata.dto.event.DocumentUploadedEvent;
import com.poliwise.metadata.dto.event.DocumentDeletedEvent;
import com.poliwise.metadata.entity.DocumentAccessRule;
import com.poliwise.metadata.entity.DocumentMetadata;
import com.poliwise.metadata.entity.DocumentTag;
import com.poliwise.metadata.entity.Tag;
import com.poliwise.metadata.enums.DocumentStatus;
import com.poliwise.metadata.enums.AccessLevel;
import com.poliwise.metadata.enums.RulePermission;
import com.poliwise.metadata.enums.RuleTargetType;
import com.poliwise.metadata.enums.UserRole;
import com.poliwise.metadata.event.MetadataEventPublisher;
import com.poliwise.metadata.exception.ResourceNotFoundException;
import com.poliwise.metadata.repository.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class DocumentMetadataService {

    private static final Logger log = LoggerFactory.getLogger(DocumentMetadataService.class);

    private final DocumentMetadataRepository metadataRepository;
    private final CategoryRepository categoryRepository;
    private final TagRepository tagRepository;
    private final DocumentTagRepository documentTagRepository;
    private final DocumentAccessRuleRepository accessRuleRepository;
    private final MetadataEventPublisher eventPublisher;

    public DocumentMetadataService(
            DocumentMetadataRepository metadataRepository,
            CategoryRepository categoryRepository,
            TagRepository tagRepository,
            DocumentTagRepository documentTagRepository,
            DocumentAccessRuleRepository accessRuleRepository,
            MetadataEventPublisher eventPublisher) {
        this.metadataRepository = metadataRepository;
        this.categoryRepository = categoryRepository;
        this.tagRepository = tagRepository;
        this.documentTagRepository = documentTagRepository;
        this.accessRuleRepository = accessRuleRepository;
        this.eventPublisher = eventPublisher;
    }

    @Transactional
    public DocumentMetadataResponse create(CreateDocumentMetadataRequest request, UUID createdBy) {
        OffsetDateTime now = OffsetDateTime.now();

        DocumentMetadata metadata = DocumentMetadata.builder()
                .id(UUID.randomUUID())
                .documentId(request.documentId())
                .title(request.title())
                .description(request.description())
                .documentType(request.documentType())
                .categoryId(request.categoryId())
                .departmentId(request.departmentId())
                .accessLevel(request.accessLevel())
                .effectiveDate(request.effectiveDate())
                .expiryDate(request.expiryDate())
                .status(DocumentStatus.DRAFT)
                .currentVersion(1)
                .createdBy(createdBy)
                .updatedBy(createdBy)
                .createdAt(now)
                .updatedAt(now)
                .build();

        DocumentMetadata saved = metadataRepository.save(metadata);

        // Add tags
        if (request.tagIds() != null && !request.tagIds().isEmpty()) {
            for (UUID tagId : request.tagIds()) {
                DocumentTag dt = DocumentTag.builder()
                        .id(UUID.randomUUID())
                        .documentMetadataId(saved.getId())
                        .tag(tagRepository.findById(tagId).orElse(null))
                        .createdAt(now)
                        .build();
                documentTagRepository.save(dt);
                tagRepository.findById(tagId).ifPresent(tag -> {
                    tag.setUsageCount(tag.getUsageCount() != null ? tag.getUsageCount() + 1 : 1);
                    tagRepository.save(tag);
                });
            }
        }

        // Add access rules
        if (request.accessRules() != null && !request.accessRules().isEmpty()) {
            for (var rule : request.accessRules()) {
                DocumentAccessRule accessRule = DocumentAccessRule.builder()
                        .id(UUID.randomUUID())
                        .documentMetadataId(saved.getId())
                        .targetType(rule.targetType())
                        .targetRole(rule.targetRole() != null
                                ? com.poliwise.metadata.enums.UserRole.valueOf(rule.targetRole())
                                : null)
                        .targetDepartmentId(rule.targetDepartmentId())
                        .targetUserId(rule.targetUserId())
                        .permission(rule.permission())
                        .createdBy(createdBy)
                        .createdAt(now)
                        .build();
                accessRuleRepository.save(accessRule);
            }
        }

        log.info("Created document metadata: id={}, documentId={}", saved.getId(), request.documentId());
        return toResponse(saved);
    }

    public DocumentMetadataResponse getById(UUID id) {
        DocumentMetadata metadata = metadataRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Document metadata not found: " + id));
        return toResponse(metadata);
    }

    public DocumentMetadataResponse getByDocumentId(UUID documentId) {
        DocumentMetadata metadata = metadataRepository.findByDocumentIdAndDeletedAtIsNull(documentId)
                .orElseThrow(() -> new ResourceNotFoundException("Document metadata not found for document: " + documentId));
        return toResponse(metadata);
    }

    @Transactional(readOnly = true)
    public DocumentAccessCheckResponse checkAccess(UUID documentId, UUID userId, UserRole userRole, UUID userDepartmentId) {
        DocumentMetadata metadata = metadataRepository.findByDocumentIdAndDeletedAtIsNull(documentId).orElse(null);
        if (metadata == null) {
            return new DocumentAccessCheckResponse(documentId, false, "metadata_not_found");
        }
        if (userRole == UserRole.ADMIN) {
            return new DocumentAccessCheckResponse(documentId, true, "admin");
        }

        List<DocumentAccessRule> rules = accessRuleRepository.findByDocumentMetadataId(metadata.getId());
        boolean denied = rules.stream().anyMatch(rule -> matchesRule(rule, userId, userRole, userDepartmentId)
                && rule.getPermission() == RulePermission.DENY);
        if (denied) {
            return new DocumentAccessCheckResponse(documentId, false, "explicit_deny");
        }

        AccessLevel level = metadata.getAccessLevel();
        if (level == AccessLevel.PUBLIC) {
            return new DocumentAccessCheckResponse(documentId, true, "public");
        }
        if (level == AccessLevel.DEPARTMENT_ONLY) {
            boolean sameDepartment = metadata.getDepartmentId() != null
                    && metadata.getDepartmentId().equals(userDepartmentId);
            return new DocumentAccessCheckResponse(documentId, sameDepartment,
                    sameDepartment ? "department_match" : "department_mismatch");
        }

        boolean allowed = rules.stream().anyMatch(rule -> matchesRule(rule, userId, userRole, userDepartmentId)
                && rule.getPermission() == RulePermission.VIEW);
        return new DocumentAccessCheckResponse(documentId, allowed, allowed ? "explicit_allow" : "restricted");
    }

    private boolean matchesRule(DocumentAccessRule rule, UUID userId, UserRole userRole, UUID userDepartmentId) {
        if (rule.getTargetType() == RuleTargetType.USER) {
            return userId != null && userId.equals(rule.getTargetUserId());
        }
        if (rule.getTargetType() == RuleTargetType.ROLE) {
            return userRole != null && userRole.equals(rule.getTargetRole());
        }
        if (rule.getTargetType() == RuleTargetType.DEPARTMENT) {
            return userDepartmentId != null && userDepartmentId.equals(rule.getTargetDepartmentId());
        }
        return false;
    }

    @Transactional
    public DocumentMetadataResponse update(UUID id, UpdateDocumentMetadataRequest request, UUID updatedBy) {
        DocumentMetadata metadata = metadataRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Document metadata not found: " + id));

        metadata.setTitle(request.title());
        metadata.setDescription(request.description());
        metadata.setDocumentType(request.documentType());
        metadata.setCategoryId(request.categoryId());
        metadata.setDepartmentId(request.departmentId());
        if (request.accessLevel() != null) {
            metadata.setAccessLevel(request.accessLevel());
        }
        metadata.setEffectiveDate(request.effectiveDate());
        metadata.setExpiryDate(request.expiryDate());
        metadata.setUpdatedBy(updatedBy);
        metadata.setUpdatedAt(OffsetDateTime.now());

        DocumentMetadata saved = metadataRepository.save(metadata);
        log.info("Updated document metadata: id={}", id);
        return toResponse(saved);
    }

    @Transactional
    public DocumentMetadataResponse publish(UUID id, UUID publishedBy) {
        DocumentMetadata metadata = metadataRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Document metadata not found: " + id));

        metadata.setStatus(DocumentStatus.PUBLISHED);
        metadata.setPublishedBy(publishedBy);
        metadata.setPublishedAt(OffsetDateTime.now());
        metadata.setUpdatedBy(publishedBy);
        metadata.setUpdatedAt(OffsetDateTime.now());

        DocumentMetadata saved = metadataRepository.save(metadata);
        log.info("Published document metadata: id={}", id);
        return toResponse(saved);
    }

    @Transactional
    public DocumentMetadataResponse archive(UUID id, UUID archivedBy) {
        DocumentMetadata metadata = metadataRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Document metadata not found: " + id));

        metadata.setStatus(DocumentStatus.ARCHIVED);
        metadata.setUpdatedBy(archivedBy);
        metadata.setUpdatedAt(OffsetDateTime.now());

        DocumentMetadata saved = metadataRepository.save(metadata);
        log.info("Archived document metadata: id={}", id);
        return toResponse(saved);
    }

    @Transactional
    public void softDelete(UUID id) {
        DocumentMetadata metadata = metadataRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Document metadata not found: " + id));

        metadata.setDeletedAt(OffsetDateTime.now());
        metadata.setUpdatedAt(OffsetDateTime.now());
        metadataRepository.save(metadata);

        eventPublisher.publishDocumentDeleted(
                DocumentDeletedEvent.create(metadata.getDocumentId(), metadata.getUpdatedBy())
        );

        log.info("Soft deleted document metadata: id={}", id);
    }

    public List<DocumentMetadataResponse> findExpired() {
        return metadataRepository.findExpiredDocuments(java.time.LocalDate.now())
                .stream()
                .map(this::toResponse)
                .toList();
    }

    public List<DocumentMetadataResponse> findByStatus(DocumentStatus status) {
        return metadataRepository.findByStatus(status)
                .stream()
                .map(this::toResponse)
                .toList();
    }

    public List<DocumentMetadataResponse> findByCategory(UUID categoryId) {
        return metadataRepository.findByCategoryId(categoryId)
                .stream()
                .map(this::toResponse)
                .toList();
    }

    private DocumentMetadataResponse toResponse(DocumentMetadata metadata) {
        String categoryName = metadata.getCategoryId() != null
                ? categoryRepository.findById(metadata.getCategoryId())
                .map(c -> c.getName()).orElse(null)
                : null;

        List<TagResponse> tags = documentTagRepository.findByDocumentMetadataId(metadata.getId())
                .stream()
                .map(dt -> dt.getTag() != null ? tagRepository.findById(dt.getTag().getId()).orElse(null) : null)
                .filter(t -> t != null)
                .map(tag -> new TagResponse(
                        tag.getId(), tag.getName(), tag.getSlug(),
                        tag.getColor(), tag.getUsageCount(), tag.getCreatedAt()))
                .toList();

        List<AccessRuleResponse> rules = accessRuleRepository.findByDocumentMetadataId(metadata.getId())
                .stream()
                .map(rule -> new AccessRuleResponse(
                        rule.getId(), rule.getDocumentMetadataId(),
                        rule.getTargetType() != null ? rule.getTargetType().name() : null,
                        rule.getTargetRole() != null ? rule.getTargetRole().name() : null,
                        rule.getTargetDepartmentId(),
                        null,
                        rule.getTargetUserId(),
                        null,
                        rule.getPermission() != null ? rule.getPermission().name() : null,
                        rule.getCreatedBy(), rule.getCreatedAt()))
                .toList();

        return DocumentMetadataResponse.from(
                metadata, categoryName, null, null, tags, rules
        );
    }
}
