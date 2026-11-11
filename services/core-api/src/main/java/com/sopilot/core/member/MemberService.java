package com.sopilot.core.member;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.identity.RefreshTokenService;
import com.sopilot.core.department.DepartmentRepository;
import com.sopilot.core.department.DepartmentRepository.Department;
import com.sopilot.core.department.DepartmentRepository.DepartmentStatus;
import com.sopilot.core.department.PublisherRepository;
import com.sopilot.core.member.MemberRepository.Member;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.workspace.WorkspaceRepository;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipRecord;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import com.sopilot.core.security.WorkspaceRole;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/**
 * Member profiles and the suspend/reactivate/remove lifecycle (FR-04, FR-22, ADR-007 §4.2, TECH §3.2).
 * Rules enforced here because constraints cannot express them: the workspace always keeps at least one
 * ACTIVE OWNER (checked under a row lock on the owners), and an ADMIN cannot suspend or remove an OWNER.
 * Role changes follow the same rules (V2-30): only an OWNER promotes to or demotes from OWNER, and every role
 * change ends the member's sessions. The acting role is read from the database, not the token, so an owner
 * demoted a minute ago cannot keep acting as one. Leaving a workspace never deletes the global account.
 */
@Service
public class MemberService {

    static final Set<String> PATCHABLE = Set.of("displayName", "employeeCode", "jobTitle", "departmentId", "role");

    private final MemberRepository members;
    private final WorkspaceRepository workspaces;
    private final DepartmentRepository departments;
    private final PublisherRepository publishers;
    private final AuditService audit;
    private final TenantTx tenant;
    private final RefreshTokenService refreshTokens;

    public MemberService(MemberRepository members, WorkspaceRepository workspaces, DepartmentRepository departments,
                         PublisherRepository publishers, AuditService audit, TenantTx tenant,
                         RefreshTokenService refreshTokens) {
        this.members = members;
        this.workspaces = workspaces;
        this.departments = departments;
        this.publishers = publishers;
        this.audit = audit;
        this.tenant = tenant;
        this.refreshTokens = refreshTokens;
    }

    public List<Member> list(AuthPrincipal principal, MembershipStatus status, UUID departmentId, String query) {
        principal.requireManager();
        return tenant.run(principal, () -> members.search(principal.workspaceId(), status, departmentId, query));
    }

    /** {@code departmentId} is the department the member publishes for, if any (a member has one department). */
    public record Me(Member member, boolean workspacePublisher, UUID publisherDepartmentId) {
    }

    /** The caller's profile and what they publish; the frontend only uses it to show or hide write buttons. */
    public Me me(AuthPrincipal principal) {
        return tenant.run(principal, () -> {
            Member member = members.find(principal.workspaceId(), principal.userId())
                    .orElseThrow(MemberService::notFound);
            boolean workspace = publishers.isWorkspacePublisher(principal.workspaceId(), principal.userId());
            UUID department = publishers.departmentsPublishedBy(principal.workspaceId(), principal.userId())
                    .stream().findFirst().orElse(null);
            return new Me(member, workspace, department);
        });
    }

    /** {@code patch} holds only the keys the client sent; an explicit null clears the optional field. */
    public Member updateProfile(AuthPrincipal principal, UUID userId, Map<String, Object> patch) {
        principal.requireManager();
        validateKeys(patch);
        return tenant.run(principal, () -> {
            WorkspaceRole actor = currentManagerRole(principal);
            Member current = members.find(principal.workspaceId(), userId).orElseThrow(MemberService::notFound);
            WorkspaceRole role = patch.containsKey("role") ? parseRole(patch.get("role")) : current.role();
            String displayName = patch.containsKey("displayName")
                    ? optionalText(patch.get("displayName"), 100, "displayName") : current.displayName();
            String employeeCode = patch.containsKey("employeeCode")
                    ? optionalText(patch.get("employeeCode"), 50, "employeeCode") : current.employeeCode();
            String jobTitle = patch.containsKey("jobTitle")
                    ? optionalText(patch.get("jobTitle"), 100, "jobTitle") : current.jobTitle();
            UUID departmentId = patch.containsKey("departmentId")
                    ? requireAssignable(principal.workspaceId(), patch.get("departmentId"), current.departmentId())
                    : current.departmentId();
            if (role != current.role()) {
                changeRole(principal, actor, current, role);
            }
            try {
                members.updateProfile(principal.workspaceId(), userId, displayName, employeeCode, jobTitle,
                        departmentId);
            } catch (DuplicateKeyException e) {
                throw new ApiException(HttpStatus.CONFLICT, "EMPLOYEE_CODE_TAKEN",
                        "Another member already has this employee code.");
            }
            if (!Objects.equals(current.departmentId(), departmentId)) {
                Map<String, Object> details = new LinkedHashMap<>();
                details.put("from", current.departmentId());
                details.put("to", departmentId);
                audit.record(principal, "MEMBER_DEPARTMENT_CHANGED", "MEMBER", userId, details);
                // Publishing is tied to the department: moving away ends it in the same transaction (TECH §15.3).
                for (UUID left : publishers.deleteDepartmentPublishingExcept(principal.workspaceId(), userId,
                        departmentId)) {
                    audit.record(principal, "PUBLISHER_UNASSIGNED", "DEPARTMENT", left,
                            publisherDetails(userId, "DEPARTMENT_CHANGED"));
                }
            }
            List<String> changed = new java.util.ArrayList<>();
            if (!Objects.equals(current.displayName(), displayName)) {
                changed.add("displayName");
            }
            if (!Objects.equals(current.employeeCode(), employeeCode)) {
                changed.add("employeeCode");
            }
            if (!Objects.equals(current.jobTitle(), jobTitle)) {
                changed.add("jobTitle");
            }
            if (!changed.isEmpty()) {
                audit.record(principal, "MEMBER_PROFILE_UPDATED", "MEMBER", userId, Map.of("fields", changed));
            }
            return members.find(principal.workspaceId(), userId).orElseThrow();
        });
    }

    public void suspend(AuthPrincipal principal, UUID userId) {
        principal.requireManager();
        tenant.runVoid(principal.workspaceId(), principal.userId(), () -> {
            WorkspaceRole actor = currentManagerRole(principal);
            Member target = members.find(principal.workspaceId(), userId).orElseThrow(MemberService::notFound);
            requireCanActOn(actor, target);
            if (target.status() == MembershipStatus.SUSPENDED) {
                return;
            }
            guardLastOwner(principal.workspaceId(), target);
            members.setSuspended(principal.workspaceId(), userId, true);
            refreshTokens.revokeForMembership(userId, principal.workspaceId(), "SUSPENDED");
            audit.record(principal, "MEMBER_SUSPENDED", "MEMBER", userId, Map.of());
        });
    }

    public void reactivate(AuthPrincipal principal, UUID userId) {
        principal.requireManager();
        tenant.runVoid(principal.workspaceId(), principal.userId(), () -> {
            WorkspaceRole actor = currentManagerRole(principal);
            Member target = members.find(principal.workspaceId(), userId).orElseThrow(MemberService::notFound);
            requireCanActOn(actor, target);
            if (target.status() == MembershipStatus.ACTIVE) {
                return;
            }
            members.setSuspended(principal.workspaceId(), userId, false);
            audit.record(principal, "MEMBER_REACTIVATED", "MEMBER", userId, Map.of());
        });
    }

    public void remove(AuthPrincipal principal, UUID userId) {
        principal.requireManager();
        tenant.runVoid(principal.workspaceId(), principal.userId(), () -> {
            WorkspaceRole actor = currentManagerRole(principal);
            Member target = members.find(principal.workspaceId(), userId).orElseThrow(MemberService::notFound);
            requireCanActOn(actor, target);
            guardLastOwner(principal.workspaceId(), target);
            auditPublishingLost(principal, userId);
            members.delete(principal.workspaceId(), userId);
            refreshTokens.revokeForMembership(userId, principal.workspaceId(), "MEMBERSHIP_LOST");
            audit.record(principal, "MEMBER_REMOVED", "MEMBER", userId, Map.of());
        });
    }

    public void leave(AuthPrincipal principal) {
        tenant.runVoid(principal.workspaceId(), principal.userId(), () -> {
            if ("PERSONAL".equals(members.workspaceKind(principal.workspaceId()).orElse(""))) {
                throw new ApiException(HttpStatus.CONFLICT, "PERSONAL_WORKSPACE",
                        "You cannot leave your personal workspace.");
            }
            Member self = members.find(principal.workspaceId(), principal.userId())
                    .orElseThrow(MemberService::notFound);
            guardLastOwner(principal.workspaceId(), self);
            auditPublishingLost(principal, principal.userId());
            members.delete(principal.workspaceId(), principal.userId());
            refreshTokens.revokeForMembership(principal.userId(), principal.workspaceId(), "MEMBERSHIP_LOST");
            audit.record(principal, "MEMBER_REMOVED", "MEMBER", principal.userId(), Map.of("self", true));
        });
    }

    /**
     * The caller's role as it is now. The token can be 15 minutes stale, so a manager who was demoted or
     * suspended since signing in is refused here. Must run inside the transaction of the change.
     */
    private WorkspaceRole currentManagerRole(AuthPrincipal principal) {
        MembershipRecord current = workspaces.findMembership(principal.workspaceId(), principal.userId())
                .orElseThrow(MemberService::forbidden);
        if (current.status() != MembershipStatus.ACTIVE || current.role() == WorkspaceRole.MEMBER) {
            throw forbidden();
        }
        return current.role();
    }

    private static void requireCanActOn(WorkspaceRole actor, Member target) {
        if (actor == WorkspaceRole.ADMIN && target.role() == WorkspaceRole.OWNER) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "An admin cannot change an owner.");
        }
    }

    /** OWNER rules of TECH §3.2; the caller writes the profile columns afterwards in the same transaction. */
    private void changeRole(AuthPrincipal principal, WorkspaceRole actor, Member target, WorkspaceRole role) {
        requireCanActOn(actor, target);
        if (role == WorkspaceRole.OWNER && actor != WorkspaceRole.OWNER) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "Only an owner can make someone an owner.");
        }
        if (target.role() == WorkspaceRole.OWNER) {
            guardLastOwner(principal.workspaceId(), target);
        }
        members.setRole(principal.workspaceId(), target.userId(), role);
        // The role lives in the access token: end the sessions so the next sign-in carries the new one.
        refreshTokens.revokeForMembership(target.userId(), principal.workspaceId(), "MEMBERSHIP_LOST");
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("from", target.role().name());
        details.put("to", role.name());
        audit.record(principal, "MEMBER_ROLE_CHANGED", "MEMBER", target.userId(), details);
    }

    /** The publisher rows go with the membership (foreign key cascade); the audit entry has to come first. */
    private void auditPublishingLost(AuthPrincipal principal, UUID userId) {
        UUID wid = principal.workspaceId();
        for (UUID department : publishers.departmentsPublishedBy(wid, userId)) {
            audit.record(principal, "PUBLISHER_UNASSIGNED", "DEPARTMENT", department,
                    publisherDetails(userId, "MEMBER_REMOVED"));
        }
        if (publishers.isWorkspacePublisher(wid, userId)) {
            audit.record(principal, "PUBLISHER_UNASSIGNED", "WORKSPACE", wid,
                    publisherDetails(userId, "MEMBER_REMOVED"));
        }
    }

    private static Map<String, Object> publisherDetails(UUID userId, String reason) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("userId", userId);
        details.put("previousUserId", userId);
        details.put("reason", reason);
        return details;
    }

    private static WorkspaceRole parseRole(Object raw) {
        if (raw instanceof String s) {
            try {
                return WorkspaceRole.valueOf(s);
            } catch (IllegalArgumentException e) {
                // falls through to the validation error below
            }
        }
        throw invalid("role");
    }

    private static ApiException forbidden() {
        return new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "You do not have permission to do this.");
    }

    /** Must run inside the transaction that then changes {@code target}. */
    private void guardLastOwner(UUID workspaceId, Member target) {
        if (target.role() != WorkspaceRole.OWNER || target.status() != MembershipStatus.ACTIVE) {
            return;
        }
        List<UUID> owners = members.lockActiveOwners(workspaceId);
        if (owners.size() <= 1) {
            throw new ApiException(HttpStatus.CONFLICT, "LAST_OWNER", "The workspace must keep at least one active owner.");
        }
    }

    private UUID requireAssignable(UUID workspaceId, Object raw, UUID currentDepartment) {
        if (raw == null) {
            return null;
        }
        UUID id;
        try {
            id = UUID.fromString(String.valueOf(raw));
        } catch (IllegalArgumentException e) {
            throw invalid("departmentId");
        }
        if (id.equals(currentDepartment)) {
            return id;
        }
        Department department = departments.find(workspaceId, id).orElseThrow(
                () -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Department not found."));
        if (department.status() == DepartmentStatus.ARCHIVED) {
            throw new ApiException(HttpStatus.CONFLICT, "DEPARTMENT_ARCHIVED",
                    "Members cannot be assigned to an archived department.");
        }
        return id;
    }

    private static void validateKeys(Map<String, Object> patch) {
        if (patch.isEmpty() || !PATCHABLE.containsAll(patch.keySet())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
        }
    }

    private static String optionalText(Object raw, int max, String field) {
        if (raw == null) {
            return null;
        }
        if (!(raw instanceof String s)) {
            throw invalid(field);
        }
        String text = s.trim();
        if (text.isEmpty()) {
            return null;
        }
        if (text.length() > max) {
            throw invalid(field);
        }
        return text;
    }

    private static ApiException invalid(String field) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.",
                Map.of("fields", Map.of(field, "invalid")));
    }

    private static ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Member not found.");
    }
}
