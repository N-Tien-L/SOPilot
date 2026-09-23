package com.poliwise.metadata.controller;

import com.poliwise.metadata.dto.AccessRuleResponse;
import com.poliwise.metadata.dto.AccessRuleSimulationResult;
import com.poliwise.metadata.dto.CreateAccessRuleRequest;
import com.poliwise.metadata.dto.DocumentAccessCheckResponse;
import com.poliwise.metadata.dto.FilterAccessibleDocumentsRequest;
import com.poliwise.metadata.dto.FilterAccessibleDocumentsResponse;
import com.poliwise.metadata.dto.UpdateAccessRuleRequest;
import com.poliwise.metadata.security.SecurityUtils;
import com.poliwise.metadata.service.AccessRuleService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/access-rules")
public class AccessRuleController {

    private final AccessRuleService accessRuleService;

    public AccessRuleController(AccessRuleService accessRuleService) {
        this.accessRuleService = accessRuleService;
    }

    /**
     * Get access rules by metadata ID.
     */
    @GetMapping
    public ResponseEntity<List<AccessRuleResponse>> getByMetadataId(
            @RequestParam("metadataId") UUID metadataId) {
        List<AccessRuleResponse> rules = accessRuleService.getByMetadataId(metadataId);
        return ResponseEntity.ok(rules);
    }

    /**
     * Get all access rules (admin only).
     */
    @GetMapping("/all")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<AccessRuleResponse>> getAll() {
        List<AccessRuleResponse> rules = accessRuleService.getAll();
        return ResponseEntity.ok(rules);
    }

    /**
     * Create a new access rule.
     */
    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<AccessRuleResponse> create(
            @Valid @RequestBody CreateAccessRuleRequest request) {
        UUID createdBy = SecurityUtils.getCurrentUserId();
        AccessRuleResponse response = accessRuleService.create(
                request.documentId(), request, createdBy);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    /**
     * Update an existing access rule.
     */
    @PutMapping("/{ruleId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<AccessRuleResponse> update(
            @PathVariable UUID ruleId,
            @Valid @RequestBody UpdateAccessRuleRequest request) {
        UUID updatedBy = SecurityUtils.getCurrentUserId();
        AccessRuleResponse response = accessRuleService.update(ruleId, request, updatedBy);
        return ResponseEntity.ok(response);
    }

    /**
     * Delete an access rule.
     */
    @DeleteMapping("/{ruleId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> delete(@PathVariable UUID ruleId) {
        accessRuleService.delete(ruleId);
        return ResponseEntity.noContent().build();
    }

    /**
     * Get access rules by document ID (via metadata lookup).
     */
    @GetMapping("/by-document/{documentId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<AccessRuleResponse>> getByDocumentId(@PathVariable UUID documentId) {
        List<AccessRuleResponse> rules = accessRuleService.getByDocumentId(documentId);
        return ResponseEntity.ok(rules);
    }

    /**
     * Simulate and preview who in the company has access to a document.
     * Shows all users grouped by access (granted/denied) with reasons.
     */
    @GetMapping("/simulation/by-document/{documentId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<AccessRuleSimulationResult> simulateByDocumentId(@PathVariable UUID documentId) {
        AccessRuleSimulationResult result = accessRuleService.simulateAccess(documentId);
        return ResponseEntity.ok(result);
    }

    /**
     * Check if current user has access to a specific document.
     */
    @GetMapping("/check/{documentId}")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<DocumentAccessCheckResponse> checkAccess(@PathVariable UUID documentId) {
        UUID userId = SecurityUtils.getCurrentUserId();
        UUID departmentId = SecurityUtils.getCurrentDepartmentId();
        com.poliwise.metadata.enums.UserRole role = SecurityUtils.getCurrentUserRole();

        DocumentAccessCheckResponse response = accessRuleService.checkDocumentAccess(
                documentId, userId, role != null ? role.name() : null, departmentId);
        return ResponseEntity.ok(response);
    }

    /**
     * Filter documents that the current user can access from a list of document IDs.
     * Used by knowledge-service to filter document lists based on access rules.
     */
    @PostMapping("/filter-accessible")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<FilterAccessibleDocumentsResponse> filterAccessibleDocuments(
            @RequestBody FilterAccessibleDocumentsRequest request) {
        UUID userId = SecurityUtils.getCurrentUserId();
        UUID departmentId = SecurityUtils.getCurrentDepartmentId();
        com.poliwise.metadata.enums.UserRole role = SecurityUtils.getCurrentUserRole();

        FilterAccessibleDocumentsResponse response = accessRuleService.filterAccessibleDocumentsBatch(
                request.documentIds(), userId, role != null ? role.name() : null, departmentId);
        return ResponseEntity.ok(response);
    }
}
