package com.sopilot.core.department;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.department.DepartmentRepository.Department;
import com.sopilot.core.department.DepartmentRepository.DepartmentStatus;
import com.sopilot.core.department.DepartmentRepository.Usage;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tenancy.TenantTx;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Flat departments per workspace (FR-23, ADR-007 §4.1, TECH §5.4). Archiving or deleting a department
 * never changes {@code documents.visibility}: a document limited to an archived department stays limited.
 */
@Service
public class DepartmentService {

    private static final int MAX_NAME = 100;

    private final DepartmentRepository departments;
    private final AuditService audit;
    private final TenantTx tenant;

    public DepartmentService(DepartmentRepository departments, AuditService audit, TenantTx tenant) {
        this.departments = departments;
        this.audit = audit;
        this.tenant = tenant;
    }

    public List<Department> list(AuthPrincipal principal, boolean includeArchived) {
        // Members only need names to display; archived entries are an admin concern.
        boolean archived = includeArchived && principal.isManager();
        return tenant.run(principal, () -> departments.list(principal.workspaceId(), archived));
    }

    public Department create(AuthPrincipal principal, String rawName) {
        principal.requireManager();
        String name = validName(rawName);
        UUID id = UuidV7.generate();
        return tenant.run(principal, () -> {
            try {
                departments.insert(id, principal.workspaceId(), name);
            } catch (DuplicateKeyException e) {
                throw nameTaken();
            }
            audit.record(principal, "DEPARTMENT_CREATED", "DEPARTMENT", id, Map.of("name", name));
            return departments.find(principal.workspaceId(), id).orElseThrow();
        });
    }

    /** {@code name} and {@code status} are each optional; at least one must be present. */
    public Department update(AuthPrincipal principal, UUID id, String rawName, DepartmentStatus status) {
        principal.requireManager();
        if (rawName == null && status == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
        }
        String newName = rawName == null ? null : validName(rawName);
        return tenant.run(principal, () -> {
            Department current = departments.find(principal.workspaceId(), id).orElseThrow(DepartmentService::notFound);
            String name = newName == null ? current.name() : newName;
            DepartmentStatus target = status == null ? current.status() : status;
            try {
                departments.update(principal.workspaceId(), id, name, target);
            } catch (DuplicateKeyException e) {
                throw nameTaken();
            }
            if (!name.equals(current.name())) {
                audit.record(principal, "DEPARTMENT_RENAMED", "DEPARTMENT", id,
                        Map.of("from", current.name(), "to", name));
            }
            if (target != current.status()) {
                audit.record(principal, target == DepartmentStatus.ARCHIVED ? "DEPARTMENT_ARCHIVED"
                        : "DEPARTMENT_RESTORED", "DEPARTMENT", id, Map.of("name", name));
            }
            return departments.find(principal.workspaceId(), id).orElseThrow();
        });
    }

    public void delete(AuthPrincipal principal, UUID id) {
        principal.requireManager();
        tenant.runVoid(principal.workspaceId(), principal.userId(), () -> {
            Department current = departments.find(principal.workspaceId(), id).orElseThrow(DepartmentService::notFound);
            Usage usage = departments.usage(principal.workspaceId(), id);
            if (usage.inUse()) {
                throw inUse(usage);
            }
            try {
                departments.delete(principal.workspaceId(), id);
            } catch (DataIntegrityViolationException e) {
                // A reference appeared between the check and the delete; the RESTRICT FK is the backstop.
                throw inUse(departments.usage(principal.workspaceId(), id));
            }
            audit.record(principal, "DEPARTMENT_DELETED", "DEPARTMENT", id, Map.of("name", current.name()));
        });
    }

    private static String validName(String raw) {
        String name = raw == null ? "" : raw.trim();
        if (name.isEmpty() || name.length() > MAX_NAME) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Department name must be 1-100 characters.");
        }
        return name;
    }

    private static ApiException nameTaken() {
        return new ApiException(HttpStatus.CONFLICT, "DEPARTMENT_NAME_TAKEN", "A department with this name already exists.");
    }

    private static ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Department not found.");
    }

    private static ApiException inUse(Usage usage) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("members", usage.members());
        details.put("pendingInvitations", usage.pendingInvitations());
        details.put("documents", usage.documents());
        return new ApiException(HttpStatus.CONFLICT, "DEPARTMENT_IN_USE",
                "The department still has members, pending invitations or documents.", details);
    }
}
