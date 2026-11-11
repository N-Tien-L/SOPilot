package com.sopilot.core.department;

import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.department.PublisherService.Overview;
import com.sopilot.core.security.AuthPrincipal;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/** Document publishers (ADR-009, TECH §15.4). The list is for every member; changes are OWNER only. */
@RestController
@RequestMapping("/api/v1")
public class PublisherController {

    private final PublisherService service;

    public PublisherController(PublisherService service) {
        this.service = service;
    }

    @GetMapping("/publishers")
    public ApiResponse<Overview> overview(AuthPrincipal principal,
                                          @RequestParam(defaultValue = "false") boolean includeArchived) {
        return ApiResponse.of(service.overview(principal, includeArchived));
    }

    @PutMapping("/publishers/workspace")
    public ResponseEntity<Void> assignWorkspace(AuthPrincipal principal, @Valid @RequestBody AssignRequest request) {
        service.assignWorkspace(principal, request.userId());
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/publishers/workspace")
    public ResponseEntity<Void> unassignWorkspace(AuthPrincipal principal) {
        service.unassignWorkspace(principal);
        return ResponseEntity.noContent().build();
    }

    @PutMapping("/departments/{id}/publisher")
    public ResponseEntity<Void> assignDepartment(AuthPrincipal principal, @PathVariable UUID id,
                                                 @Valid @RequestBody AssignRequest request) {
        service.assignDepartment(principal, id, request.userId());
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/departments/{id}/publisher")
    public ResponseEntity<Void> unassignDepartment(AuthPrincipal principal, @PathVariable UUID id) {
        service.unassignDepartment(principal, id);
        return ResponseEntity.noContent().build();
    }

    public record AssignRequest(@NotNull UUID userId) {
    }
}
