package com.poliwise.metadata.controller;

import com.poliwise.metadata.dto.*;
import com.poliwise.metadata.security.SecurityUtils;
import com.poliwise.metadata.service.DocumentMetadataService;
import com.poliwise.metadata.service.AccessRuleService;
import com.poliwise.metadata.service.TagService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/metadata")
public class DocumentMetadataController {

    private final DocumentMetadataService metadataService;
    private final AccessRuleService accessRuleService;
    private final TagService tagService;

    public DocumentMetadataController(
            DocumentMetadataService metadataService,
            AccessRuleService accessRuleService,
            TagService tagService) {
        this.metadataService = metadataService;
        this.accessRuleService = accessRuleService;
        this.tagService = tagService;
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DocumentMetadataResponse> create(
            @Valid @RequestBody CreateDocumentMetadataRequest request) {
        UUID createdBy = SecurityUtils.getCurrentUserId();
        DocumentMetadataResponse response = metadataService.create(request, createdBy);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/document/{documentId}")
    public ResponseEntity<DocumentMetadataResponse> getByDocumentId(@PathVariable UUID documentId) {
        DocumentMetadataResponse response = metadataService.getByDocumentId(documentId);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/document/{documentId}/access-check")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<DocumentAccessCheckResponse> checkAccess(@PathVariable UUID documentId) {
        DocumentAccessCheckResponse response = metadataService.checkAccess(
                documentId,
                SecurityUtils.getCurrentUserId(),
                SecurityUtils.getCurrentUserRole(),
                SecurityUtils.getCurrentDepartmentId()
        );
        return ResponseEntity.ok(response);
    }

    @GetMapping("/status/{status}")
    public ResponseEntity<List<DocumentMetadataResponse>> getByStatus(@PathVariable String status) {
        var docStatus = com.poliwise.metadata.enums.DocumentStatus.valueOf(status.toUpperCase());
        List<DocumentMetadataResponse> response = metadataService.findByStatus(docStatus);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/category/{categoryId}")
    public ResponseEntity<List<DocumentMetadataResponse>> getByCategory(@PathVariable UUID categoryId) {
        List<DocumentMetadataResponse> response = metadataService.findByCategory(categoryId);
        return ResponseEntity.ok(response);
    }

    // ===== Tag Endpoints (under /api/v1/metadata/tags/*) =====

    @GetMapping("/tags")
    public ResponseEntity<List<TagResponse>> getAllTags() {
        return ResponseEntity.ok(tagService.getAll());
    }

    @GetMapping("/tags/active")
    public ResponseEntity<List<TagResponse>> getActiveTags() {
        return ResponseEntity.ok(tagService.getActive());
    }

    @GetMapping("/tags/popular")
    public ResponseEntity<List<TagResponse>> getPopularTags() {
        return ResponseEntity.ok(tagService.getPopular());
    }

    @PostMapping("/tags")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<TagResponse> createTag(@Valid @RequestBody CreateTagRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(tagService.create(request));
    }

    @GetMapping("/tags/{id}")
    public ResponseEntity<TagResponse> getTag(@PathVariable UUID id) {
        return ResponseEntity.ok(tagService.getById(id));
    }

    @PutMapping("/tags/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<TagResponse> updateTag(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateTagRequest request) {
        return ResponseEntity.ok(tagService.update(id, request));
    }

    @DeleteMapping("/tags/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> deleteTag(@PathVariable UUID id) {
        tagService.delete(id);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/tags/resolve")
    @PreAuthorize("hasRole('ADMIN') or hasRole('MANAGER')")
    public ResponseEntity<ResolveTagsResponse> resolveTags(@Valid @RequestBody ResolveTagsRequest request) {
        return ResponseEntity.ok(tagService.resolveTags(request.tagNames()));
    }

    @PostMapping("/{metadataId}/rules")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<AccessRuleResponse> addRule(
            @PathVariable UUID metadataId,
            @Valid @RequestBody CreateAccessRuleRequest request) {
        UUID createdBy = SecurityUtils.getCurrentUserId();
        AccessRuleResponse response = accessRuleService.create(metadataId, request, createdBy);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/{metadataId}/rules")
    public ResponseEntity<List<AccessRuleResponse>> getRules(@PathVariable UUID metadataId) {
        List<AccessRuleResponse> rules = accessRuleService.getByMetadataId(metadataId);
        return ResponseEntity.ok(rules);
    }

    @DeleteMapping("/rules/{ruleId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> deleteRule(@PathVariable UUID ruleId) {
        accessRuleService.delete(ruleId);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/{id}")
    public ResponseEntity<DocumentMetadataResponse> get(@PathVariable UUID id) {
        DocumentMetadataResponse response = metadataService.getById(id);
        return ResponseEntity.ok(response);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DocumentMetadataResponse> update(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateDocumentMetadataRequest request) {
        UUID updatedBy = SecurityUtils.getCurrentUserId();
        DocumentMetadataResponse response = metadataService.update(id, request, updatedBy);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/{id}/publish")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DocumentMetadataResponse> publish(@PathVariable UUID id) {
        UUID publishedBy = SecurityUtils.getCurrentUserId();
        DocumentMetadataResponse response = metadataService.publish(id, publishedBy);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/{id}/archive")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DocumentMetadataResponse> archive(@PathVariable UUID id) {
        UUID archivedBy = SecurityUtils.getCurrentUserId();
        DocumentMetadataResponse response = metadataService.archive(id, archivedBy);
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> delete(@PathVariable UUID id) {
        metadataService.softDelete(id);
        return ResponseEntity.noContent().build();
    }
}
