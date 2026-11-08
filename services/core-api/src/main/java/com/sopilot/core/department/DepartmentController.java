package com.sopilot.core.department;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.department.DepartmentRepository.Department;
import com.sopilot.core.department.DepartmentRepository.DepartmentStatus;
import com.sopilot.core.security.AuthPrincipal;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** Departments of the caller's workspace (TECH §5.4). The workspace is always the token's {@code wid}. */
@RestController
@RequestMapping("/api/v1/departments")
public class DepartmentController {

    private final DepartmentService service;

    public DepartmentController(DepartmentService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<List<DepartmentView>> list(AuthPrincipal principal,
                                                  @RequestParam(defaultValue = "false") boolean includeArchived) {
        return ApiResponse.of(service.list(principal, includeArchived).stream().map(DepartmentView::of).toList());
    }

    @PostMapping
    public ResponseEntity<ApiResponse<DepartmentView>> create(AuthPrincipal principal,
                                                              @Valid @RequestBody CreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.of(DepartmentView.of(service.create(principal, request.name()))));
    }

    @PatchMapping("/{id}")
    public ApiResponse<DepartmentView> update(AuthPrincipal principal, @PathVariable UUID id,
                                              @RequestBody UpdateRequest request) {
        DepartmentStatus status = null;
        if (request.status() != null) {
            try {
                status = DepartmentStatus.valueOf(request.status());
            } catch (IllegalArgumentException e) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Status must be ACTIVE or ARCHIVED.");
            }
        }
        return ApiResponse.of(DepartmentView.of(service.update(principal, id, request.name(), status)));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(AuthPrincipal principal, @PathVariable UUID id) {
        service.delete(principal, id);
        return ResponseEntity.noContent().build();
    }

    public record CreateRequest(@NotNull String name) {
    }

    public record UpdateRequest(String name, String status) {
    }

    public record DepartmentView(UUID id, String name, String status, OffsetDateTime createdAt) {
        static DepartmentView of(Department d) {
            return new DepartmentView(d.id(), d.name(), d.status().name(), d.createdAt());
        }
    }
}
