package com.sopilot.core.category;

import com.sopilot.core.category.CategoryRepository.Category;
import com.sopilot.core.category.CategoryRepository.CategoryStatus;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.ApiResponse;
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

/** Categories of the caller's workspace (TECH §5.6). Workspace comes from the access token only. */
@RestController
@RequestMapping("/api/v1/categories")
public class CategoryController {

    private final CategoryService service;

    public CategoryController(CategoryService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<List<CategoryView>> list(AuthPrincipal principal,
                                                @RequestParam(defaultValue = "false") boolean includeArchived) {
        return ApiResponse.of(service.list(principal, includeArchived).stream().map(CategoryView::of).toList());
    }

    @GetMapping("/{id}")
    public ApiResponse<CategoryView> get(AuthPrincipal principal, @PathVariable UUID id) {
        return ApiResponse.of(CategoryView.of(service.get(principal, id)));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<CategoryView>> create(AuthPrincipal principal,
                                                            @Valid @RequestBody CreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.of(CategoryView.of(service.create(principal, request.name()))));
    }

    @PatchMapping("/{id}")
    public ApiResponse<CategoryView> update(AuthPrincipal principal, @PathVariable UUID id,
                                            @RequestBody UpdateRequest request) {
        CategoryStatus status = null;
        if (request.status() != null) {
            try {
                status = CategoryStatus.valueOf(request.status());
            } catch (IllegalArgumentException e) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Status must be ACTIVE or ARCHIVED.");
            }
        }
        return ApiResponse.of(CategoryView.of(service.update(principal, id, request.name(), status)));
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

    public record CategoryView(UUID id, String name, String status, OffsetDateTime createdAt, OffsetDateTime updatedAt) {
        static CategoryView of(Category c) {
            return new CategoryView(c.id(), c.name(), c.status().name(), c.createdAt(), c.updatedAt());
        }
    }
}
