package com.sopilot.core.department;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.department.DepartmentRepository.Department;
import com.sopilot.core.department.DepartmentRepository.DepartmentStatus;
import com.sopilot.core.department.PublisherRepository.DepartmentPublisher;
import com.sopilot.core.department.PublisherRepository.Member;
import com.sopilot.core.department.PublisherRepository.PublisherRef;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tenancy.TenantTx;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Who may write documents (ADR-009, TECH §15.4): one publisher per department and one for the workspace.
 * Only an OWNER assigns, read from the database inside the transaction so an owner demoted since signing in
 * cannot. Changing a publisher takes {@code FOR UPDATE} on the row a document write holds {@code FOR SHARE}:
 * a write that started before the change finishes before it, and the previous publisher's next write is refused.
 */
@Service
public class PublisherService {

    private final PublisherRepository publishers;
    private final DepartmentRepository departments;
    private final AuditService audit;
    private final TenantTx tenant;

    public PublisherService(PublisherRepository publishers, DepartmentRepository departments, AuditService audit,
                            TenantTx tenant) {
        this.publishers = publishers;
        this.departments = departments;
        this.audit = audit;
        this.tenant = tenant;
    }

    public record Overview(PublisherRef workspace, List<DepartmentPublisher> departments) {
    }

    /** Any member. Archived departments only for managers who ask for them. */
    public Overview overview(AuthPrincipal principal, boolean includeArchived) {
        boolean archived = includeArchived && principal.isManager();
        return tenant.run(principal, () -> new Overview(
                publishers.workspacePublisher(principal.workspaceId()).orElse(null),
                publishers.departmentPublishers(principal.workspaceId(), archived)));
    }

    public void assignWorkspace(AuthPrincipal principal, UUID userId) {
        principal.requireOwner();
        UUID wid = principal.workspaceId();
        tenant.runVoid(wid, principal.userId(), () -> {
            requireCurrentOwner(principal);
            requireActiveMember(wid, userId);
            Optional<UUID> previous = publishers.lockWorkspacePublisher(wid);
            if (previous.filter(userId::equals).isPresent()) {
                return;
            }
            publishers.putWorkspacePublisher(wid, userId);
            audit.record(principal, "PUBLISHER_ASSIGNED", "WORKSPACE", wid,
                    details(userId, previous.orElse(null), "OWNER_ACTION"));
        });
    }

    public void unassignWorkspace(AuthPrincipal principal) {
        principal.requireOwner();
        UUID wid = principal.workspaceId();
        tenant.runVoid(wid, principal.userId(), () -> {
            requireCurrentOwner(principal);
            publishers.lockWorkspacePublisher(wid).ifPresent(previous -> {
                publishers.deleteWorkspacePublisher(wid);
                audit.record(principal, "PUBLISHER_UNASSIGNED", "WORKSPACE", wid,
                        details(previous, previous, "OWNER_ACTION"));
            });
        });
    }

    /** {@code 404} for a department of another workspace; then the conflicts of TECH §15.4 in that order. */
    public void assignDepartment(AuthPrincipal principal, UUID departmentId, UUID userId) {
        principal.requireOwner();
        UUID wid = principal.workspaceId();
        tenant.runVoid(wid, principal.userId(), () -> {
            requireCurrentOwner(principal);
            Department department = departments.find(wid, departmentId).orElseThrow(
                    () -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Department not found."));
            if (department.status() == DepartmentStatus.ARCHIVED) {
                throw new ApiException(HttpStatus.CONFLICT, "DEPARTMENT_ARCHIVED",
                        "An archived department cannot get a publisher.");
            }
            Member member = requireActiveMember(wid, userId);
            if (!departmentId.equals(member.departmentId())) {
                throw new ApiException(HttpStatus.CONFLICT, "PUBLISHER_NOT_IN_DEPARTMENT",
                        "A publisher must belong to the department.");
            }
            Optional<UUID> previous = publishers.lockDepartmentPublisher(wid, departmentId);
            if (previous.filter(userId::equals).isPresent()) {
                return;
            }
            publishers.putDepartmentPublisher(wid, departmentId, userId);
            audit.record(principal, "PUBLISHER_ASSIGNED", "DEPARTMENT", departmentId,
                    details(userId, previous.orElse(null), "OWNER_ACTION"));
        });
    }

    /** Idempotent: a department without a publisher is a success. */
    public void unassignDepartment(AuthPrincipal principal, UUID departmentId) {
        principal.requireOwner();
        UUID wid = principal.workspaceId();
        tenant.runVoid(wid, principal.userId(), () -> {
            requireCurrentOwner(principal);
            departments.find(wid, departmentId).orElseThrow(
                    () -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Department not found."));
            publishers.lockDepartmentPublisher(wid, departmentId).ifPresent(previous -> {
                publishers.deleteDepartmentPublisher(wid, departmentId);
                audit.record(principal, "PUBLISHER_UNASSIGNED", "DEPARTMENT", departmentId,
                        details(previous, previous, "OWNER_ACTION"));
            });
        });
    }

    private void requireCurrentOwner(AuthPrincipal principal) {
        boolean owner = publishers.member(principal.workspaceId(), principal.userId()).map(Member::isOwner)
                .orElse(false);
        if (!owner) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "You do not have permission to do this.");
        }
    }

    /** Locks the membership {@code FOR SHARE} so a concurrent move or suspension cannot slip in after the check. */
    private Member requireActiveMember(UUID workspaceId, UUID userId) {
        return publishers.lockMemberShared(workspaceId, userId).filter(Member::active).orElseThrow(
                () -> new ApiException(HttpStatus.CONFLICT, "MEMBER_NOT_ACTIVE",
                        "The person must be an active member of the workspace."));
    }

    static Map<String, Object> details(UUID userId, UUID previousUserId, String reason) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("userId", userId);
        details.put("previousUserId", previousUserId);
        details.put("reason", reason);
        return details;
    }
}
