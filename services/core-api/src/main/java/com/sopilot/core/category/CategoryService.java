package com.sopilot.core.category;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.category.CategoryRepository.Category;
import com.sopilot.core.category.CategoryRepository.CategoryStatus;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tenancy.TenantTx;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Flat categories per workspace (TECH §3.4, §5.6). Read is open to all workspace members;
 * writes require OWNER or ADMIN.
 */
@Service
public class CategoryService {

    private static final int MAX_NAME = 100;

    private final CategoryRepository categories;
    private final AuditService audit;
    private final TenantTx tenant;

    public CategoryService(CategoryRepository categories, AuditService audit, TenantTx tenant) {
        this.categories = categories;
        this.audit = audit;
        this.tenant = tenant;
    }

    public List<Category> list(AuthPrincipal principal, boolean includeArchived) {
        boolean archived = includeArchived && principal.isManager();
        return tenant.run(principal, () -> categories.list(principal.workspaceId(), archived));
    }

    public Category get(AuthPrincipal principal, UUID id) {
        return tenant.run(principal, () -> categories.find(principal.workspaceId(), id)
                .orElseThrow(CategoryService::notFound));
    }

    public Category create(AuthPrincipal principal, String rawName) {
        principal.requireManager();
        String name = validName(rawName);
        UUID id = UuidV7.generate();
        return tenant.run(principal, () -> {
            try {
                categories.insert(id, principal.workspaceId(), name);
            } catch (DuplicateKeyException e) {
                throw nameTaken();
            }
            audit.record(principal, "CATEGORY_CREATED", "CATEGORY", id, Map.of("name", name));
            return categories.find(principal.workspaceId(), id).orElseThrow();
        });
    }

    public Category update(AuthPrincipal principal, UUID id, String rawName, CategoryStatus status) {
        principal.requireManager();
        if (rawName == null && status == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
        }
        String newName = rawName == null ? null : validName(rawName);
        return tenant.run(principal, () -> {
            Category current = categories.find(principal.workspaceId(), id).orElseThrow(CategoryService::notFound);
            String name = newName == null ? current.name() : newName;
            CategoryStatus target = status == null ? current.status() : status;
            try {
                categories.update(principal.workspaceId(), id, name, target);
            } catch (DuplicateKeyException e) {
                throw nameTaken();
            }
            if (!name.equals(current.name())) {
                audit.record(principal, "CATEGORY_RENAMED", "CATEGORY", id,
                        Map.of("from", current.name(), "to", name));
            }
            if (target != current.status()) {
                audit.record(principal, target == CategoryStatus.ARCHIVED ? "CATEGORY_ARCHIVED"
                        : "CATEGORY_RESTORED", "CATEGORY", id, Map.of("name", name));
            }
            return categories.find(principal.workspaceId(), id).orElseThrow();
        });
    }

    public void delete(AuthPrincipal principal, UUID id) {
        principal.requireManager();
        tenant.runVoid(principal.workspaceId(), principal.userId(), () -> {
            Category current = categories.find(principal.workspaceId(), id).orElseThrow(CategoryService::notFound);
            categories.delete(principal.workspaceId(), id);
            audit.record(principal, "CATEGORY_DELETED", "CATEGORY", id, Map.of("name", current.name()));
        });
    }

    public static String validName(String raw) {
        if (raw == null) {
            throw invalidName();
        }
        String trimmed = raw.strip();
        if (trimmed.isEmpty() || trimmed.length() > MAX_NAME) {
            throw invalidName();
        }
        return trimmed;
    }

    private static ApiException invalidName() {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Category name is invalid.",
                Map.of("fields", Map.of("name", "Name must be between 1 and " + MAX_NAME + " characters.")));
    }

    private static ApiException nameTaken() {
        return new ApiException(HttpStatus.CONFLICT, "CATEGORY_NAME_TAKEN",
                "A category with this name already exists in the workspace.");
    }

    public static ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Category not found.");
    }
}
