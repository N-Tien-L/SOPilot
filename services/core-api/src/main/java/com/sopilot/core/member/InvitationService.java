package com.sopilot.core.member;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.config.SopilotProperties;
import com.sopilot.core.department.DepartmentRepository;
import com.sopilot.core.department.DepartmentRepository.Department;
import com.sopilot.core.department.DepartmentRepository.DepartmentStatus;
import com.sopilot.core.identity.IdentityService.LoginSession;
import com.sopilot.core.identity.WorkspaceSessionService;
import com.sopilot.core.member.InvitationRepository.Acceptance;
import com.sopilot.core.member.InvitationRepository.Invitation;
import com.sopilot.core.member.InvitationRepository.State;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.security.WorkspaceRole;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.workspace.WorkspaceRepository;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipRecord;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Invitations to a workspace (FR-04, TECH-V2-core-api §5.3, ADR-005). The link carries a 256-bit random
 * token that is stored only as its SHA-256 and shown once, in the create response; it is single use,
 * expires after 7 days and can be revoked. core-api sends no email: the inviter shares the link.
 * Redeeming runs in one transaction with the session switch, so a failed token issue leaves the
 * invitation unused.
 */
@Service
public class InvitationService {

    static final int VALIDITY_DAYS = 7;
    private static final int MAX_EMAIL = 254;
    private static final int MAX_TOKEN = 128;
    private static final Pattern EMAIL = Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");
    private static final SecureRandom RANDOM = new SecureRandom();

    private final InvitationRepository invitations;
    private final DepartmentRepository departments;
    private final WorkspaceRepository workspaces;
    private final AuditService audit;
    private final TenantTx tenant;
    private final TransactionTemplate tx;
    private final WorkspaceSessionService sessions;
    private final String frontendOrigin;

    public InvitationService(InvitationRepository invitations, DepartmentRepository departments,
                             WorkspaceRepository workspaces, AuditService audit, TenantTx tenant,
                             TransactionTemplate tx, WorkspaceSessionService sessions,
                             SopilotProperties properties) {
        this.invitations = invitations;
        this.departments = departments;
        this.workspaces = workspaces;
        this.audit = audit;
        this.tenant = tenant;
        this.tx = tx;
        this.sessions = sessions;
        this.frontendOrigin = properties.auth().frontendOrigin().replaceAll("/+$", "");
    }

    /** The inviter's request; {@code departmentId}, names and codes are optional. */
    public record CreateCommand(String email, String role, String displayName, UUID departmentId,
                                String employeeCode, String jobTitle) {
    }

    /** {@code inviteUrl} holds the secret token; it is returned once and never stored in clear. */
    public record Created(UUID id, OffsetDateTime expiresAt, String inviteUrl) {
        @Override
        public String toString() {
            return "Created[id=" + id + ", expiresAt=" + expiresAt + ", inviteUrl=<redacted>]";
        }
    }

    public List<Invitation> listPending(AuthPrincipal principal) {
        principal.requireManager();
        return tenant.run(principal, () -> {
            requireCurrentManager(principal);
            return invitations.listPending(principal.workspaceId());
        });
    }

    public Created create(AuthPrincipal principal, CreateCommand command) {
        principal.requireManager();
        String email = normalizeEmail(command.email());
        String role = parseInvitedRole(command.role());
        String displayName = optionalText(command.displayName(), 100, "displayName");
        String employeeCode = optionalText(command.employeeCode(), 50, "employeeCode");
        String jobTitle = optionalText(command.jobTitle(), 100, "jobTitle");

        String token = newToken();
        OffsetDateTime expiresAt = OffsetDateTime.now(ZoneOffset.UTC).plusDays(VALIDITY_DAYS);
        UUID id = UuidV7.generate();
        UUID workspaceId = principal.workspaceId();
        return tenant.run(principal, () -> {
            requireCurrentManager(principal);
            if (command.departmentId() != null) {
                Department department = departments.find(workspaceId, command.departmentId()).orElseThrow(
                        () -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Department not found."));
                if (department.status() == DepartmentStatus.ARCHIVED) {
                    throw new ApiException(HttpStatus.CONFLICT, "DEPARTMENT_ARCHIVED",
                            "Members cannot be invited to an archived department.");
                }
            }
            if (invitations.memberEmailExists(workspaceId, email)) {
                throw new ApiException(HttpStatus.CONFLICT, "ALREADY_MEMBER",
                        "This person is already a member of the workspace.");
            }
            if (employeeCode != null && invitations.employeeCodeTaken(workspaceId, employeeCode)) {
                throw employeeCodeTaken();
            }
            invitations.revokeExpiredFor(workspaceId, email);
            if (invitations.pendingEmailExists(workspaceId, email)) {
                throw pending();
            }
            try {
                invitations.insert(id, workspaceId, email, role, displayName, employeeCode, jobTitle,
                        command.departmentId(), hash(token), principal.userId(), expiresAt);
            } catch (DuplicateKeyException e) {
                // A concurrent request for the same email won the unique index; the token hash cannot collide.
                throw pending();
            }
            Map<String, Object> details = new LinkedHashMap<>();
            details.put("email", email);
            details.put("role", role);
            details.put("departmentId", command.departmentId());
            audit.record(principal, "INVITATION_CREATED", "INVITATION", id, details);
            return new Created(id, expiresAt, frontendOrigin + "/invite#token=" + token);
        });
    }

    /** Idempotent: revoking a revoked invitation succeeds; a used one is {@code 409}. */
    public void revoke(AuthPrincipal principal, UUID invitationId) {
        principal.requireManager();
        tenant.runVoid(principal.workspaceId(), principal.userId(), () -> {
            requireCurrentManager(principal);
            State state = invitations.lockState(principal.workspaceId(), invitationId).orElseThrow(
                    () -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Invitation not found."));
            if (state.accepted()) {
                throw new ApiException(HttpStatus.CONFLICT, "INVITATION_ALREADY_USED",
                        "This invitation was already accepted.");
            }
            if (state.revoked()) {
                return;
            }
            invitations.revoke(principal.workspaceId(), invitationId);
            audit.record(principal, "INVITATION_REVOKED", "INVITATION", invitationId, Map.of());
        });
    }

    /**
     * Redeems by link token or by the id listed after login (exactly one). The caller's own workspace in the
     * token is irrelevant; the target workspace comes from the invitation row, found through the definer
     * function. Replaying a link by the same user who already redeemed it is a no-op that signs them in again.
     */
    public LoginSession accept(AuthPrincipal principal, String token, UUID invitationId,
                               String currentRefreshToken) {
        boolean hasToken = token != null && !token.isBlank();
        if (hasToken == (invitationId != null)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
        }
        if (hasToken && token.length() > MAX_TOKEN) {
            throw notFound();
        }
        byte[] tokenHash = hasToken ? hash(token.trim()) : null;
        return tx.execute(status -> {
            Acceptance result = invitations.accept(principal.userId(), tokenHash, invitationId);
            switch (result.outcome()) {
                case "ACCEPTED" -> tenant.runVoid(result.workspaceId(), principal.userId(), () -> {
                    Map<String, Object> details = new LinkedHashMap<>();
                    details.put("role", result.role());
                    details.put("departmentId", result.departmentId());
                    details.put("departmentDropped", result.departmentDropped());
                    audit.record(result.workspaceId(), principal.userId(), "INVITATION_ACCEPTED", "INVITATION",
                            result.invitationId(), details);
                });
                case "ALREADY_ACCEPTED" -> { }
                case "NOT_FOUND" -> throw notFound();
                case "REVOKED" -> throw new ApiException(HttpStatus.GONE, "INVITATION_REVOKED",
                        "This invitation was revoked.");
                case "EXPIRED" -> throw new ApiException(HttpStatus.GONE, "INVITATION_EXPIRED",
                        "This invitation has expired.");
                case "EMAIL_MISMATCH" -> throw new ApiException(HttpStatus.CONFLICT, "INVITATION_EMAIL_MISMATCH",
                        "This invitation was sent to a different email address.");
                case "ALREADY_USED" -> throw new ApiException(HttpStatus.CONFLICT, "INVITATION_ALREADY_USED",
                        "This invitation was already accepted.");
                case "EMPLOYEE_CODE_TAKEN" -> throw employeeCodeTaken();
                default -> throw new IllegalStateException("Unknown invitation outcome");
            }
            return sessions.switchTo(principal.userId(), result.workspaceId(), currentRefreshToken);
        });
    }

    /** The inviter's role as it is now; a token issued before a demotion or suspension no longer counts. */
    private void requireCurrentManager(AuthPrincipal principal) {
        MembershipRecord current = workspaces.findMembership(principal.workspaceId(), principal.userId())
                .orElse(null);
        if (current == null || current.status() != MembershipStatus.ACTIVE || current.role() == WorkspaceRole.MEMBER) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "You do not have permission to do this.");
        }
    }

    static String newToken() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    static byte[] hash(String token) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable");
        }
    }

    static String normalizeEmail(String raw) {
        String email = raw == null ? "" : raw.trim().toLowerCase(java.util.Locale.ROOT);
        if (email.isEmpty() || email.length() > MAX_EMAIL || !EMAIL.matcher(email).matches()) {
            throw invalid("email");
        }
        return email;
    }

    /** Never OWNER: an owner is made by an existing owner through a role change (ADR-005). */
    static String parseInvitedRole(String raw) {
        if ("ADMIN".equals(raw) || "MEMBER".equals(raw)) {
            return raw;
        }
        throw invalid("role");
    }

    static String optionalText(String raw, int max, String field) {
        if (raw == null) {
            return null;
        }
        String text = raw.trim();
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

    private static ApiException pending() {
        return new ApiException(HttpStatus.CONFLICT, "INVITATION_PENDING",
                "This email already has a pending invitation.");
    }

    private static ApiException employeeCodeTaken() {
        return new ApiException(HttpStatus.CONFLICT, "EMPLOYEE_CODE_TAKEN",
                "Another member already has this employee code.");
    }

    private static ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Invitation not found.");
    }
}
