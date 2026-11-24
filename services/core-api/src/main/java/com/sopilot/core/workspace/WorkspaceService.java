package com.sopilot.core.workspace;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.document.DocumentRepository;
import com.sopilot.core.document.DocumentRepository.Usage;
import com.sopilot.core.document.DocumentService;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.workspace.WorkspaceRepository.UserProfile;
import com.sopilot.core.workspace.WorkspaceRepository.WorkspaceKind;
import com.sopilot.core.workspace.WorkspaceRepository.WorkspaceRecord;
import com.sopilot.core.workspace.WorkspaceRepository.WorkspaceSummary;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Workspace CRUD for the caller (FR-03; TECH-V2-core-api §5.2). Management endpoints act on the
 * workspace of the verified token ({@code /current}); no workspace id is accepted from the client.
 * Switching workspaces and issuing the matching tokens is {@code identity.WorkspaceSessionService}.
 */
@Service
public class WorkspaceService {

    private static final int MAX_NAME = 100;

    private final WorkspaceRepository workspaces;
    private final DocumentRepository documents;
    private final DocumentService documentService;
    private final AuditService audit;
    private final TenantTx tenant;

    public WorkspaceService(WorkspaceRepository workspaces, DocumentRepository documents,
                            DocumentService documentService, AuditService audit, TenantTx tenant) {
        this.workspaces = workspaces;
        this.documents = documents;
        this.documentService = documentService;
        this.audit = audit;
        this.tenant = tenant;
    }

    /** Workspaces of the caller, active and suspended memberships alike. */
    public List<WorkspaceSummary> listMine(AuthPrincipal principal) {
        return tenant.run(null, principal.userId(), () -> workspaces.listForUser(principal.userId()));
    }

    /** Creates a TEAM workspace owned by {@code userId} and returns its id. The caller then issues the tokens. */
    public UUID createTeam(UUID userId, String rawName) {
        String name = validName(rawName);
        UUID workspaceId = UuidV7.generate();
        // The new workspace is the RLS tenant of its own first rows (WITH CHECK id = current_workspace()).
        tenant.runVoid(workspaceId, userId, () -> {
            UserProfile profile = workspaces.findUserProfile(userId)
                    .orElseThrow(() -> new IllegalStateException("User row is missing"));
            workspaces.insertTeamWorkspace(workspaceId, name, userId);
            workspaces.insertOwnerMembership(workspaceId, userId, profile.email(), profile.displayName());
            workspaces.insertWorkspacePublisher(workspaceId, userId);
            audit.record(workspaceId, userId, "WORKSPACE_CREATED", "WORKSPACE", workspaceId, Map.of("name", name));
        });
        return workspaceId;
    }

    public Detail current(AuthPrincipal principal) {
        UUID wid = principal.workspaceId();
        return tenant.run(principal, () -> {
            WorkspaceRecord workspace = workspaces.findVisible(wid).orElseThrow(WorkspaceService::notFound);
            Usage usage = documents.usage(wid);
            return new Detail(workspace.id(), workspace.name(), workspace.kind(), principal.role().name(),
                    usage.documents(), usage.bytes());
        });
    }

    public Detail rename(AuthPrincipal principal, String rawName) {
        principal.requireOwner();
        String name = validName(rawName);
        UUID wid = principal.workspaceId();
        tenant.runVoid(wid, principal.userId(), () -> {
            if (workspaces.rename(wid, name) == 0) {
                throw notFound();
            }
            audit.record(principal, "WORKSPACE_RENAMED", "WORKSPACE", wid, Map.of("name", name));
        });
        return current(principal);
    }

    /**
     * Soft delete (TECH §5.2): every document gets a {@code DOCUMENT_DELETED} event so ai-service drops its
     * chunks, and the workspace disappears for its members. Their refresh tokens stop working at the next refresh
     * because a deleted workspace has no usable membership; access tokens already issued last at most 15 minutes.
     */
    public void delete(AuthPrincipal principal) {
        principal.requireOwner();
        UUID wid = principal.workspaceId();
        tenant.runVoid(wid, principal.userId(), () -> {
            WorkspaceRecord workspace = workspaces.findVisible(wid).orElseThrow(WorkspaceService::notFound);
            if (workspace.kind() == WorkspaceKind.PERSONAL) {
                throw new ApiException(HttpStatus.CONFLICT, "PERSONAL_WORKSPACE",
                        "A personal workspace cannot be deleted.");
            }
            int removedDocuments = documentService.deleteAll(principal);
            workspaces.softDelete(wid);
            audit.record(principal, "WORKSPACE_DELETED", "WORKSPACE", wid, Map.of("documents", removedDocuments));
        });
    }

    private static String validName(String raw) {
        String name = raw == null ? "" : raw.trim();
        if (name.isEmpty() || name.length() > MAX_NAME) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED",
                    "Workspace name must be 1 to " + MAX_NAME + " characters.");
        }
        return name;
    }

    private static ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Workspace not found.");
    }

    public record Detail(UUID id, String name, WorkspaceKind kind, String role, long documentCount, long bytesUsed) {
    }
}
