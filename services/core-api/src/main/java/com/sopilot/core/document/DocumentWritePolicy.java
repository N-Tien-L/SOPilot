package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.department.PublisherRepository;
import com.sopilot.core.department.PublisherRepository.Member;
import com.sopilot.core.security.AuthPrincipal;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.HashSet;

/**
 * The only place that decides who may write a document (ADR-009, TECH-V2-core-api §15.3). A document is written
 * by the publisher of its owning department ({@code DEPARTMENTS}) or of the workspace ({@code WORKSPACE}); an
 * OWNER may additionally delete any document and transfer responsibility, but never writes content. ADMIN
 * has no write access through the role.
 *
 * <p>Everything here reads the database inside the caller's tenant transaction and ignores {@code wrole} and
 * {@code wdept} of the token, so a change of publisher or role applies to the next request without a refresh.
 * The publisher row is locked {@code FOR SHARE}: changing the publisher waits for a write in flight.
 * Callers load the document (and apply the read filter, {@code 404}) before asking, so an unreadable document
 * never reaches the {@code 403}.
 */
@Component
public class DocumentWritePolicy {

    /** In which capacity the caller wrote; recorded in the audit entry ({@code details.actingAs}). */
    public enum ActingAs { WORKSPACE_PUBLISHER, DEPARTMENT_PUBLISHER, OWNER }

    private final PublisherRepository publishers;

    public DocumentWritePolicy(PublisherRepository publishers) {
        this.publishers = publishers;
    }

    /** Edit, replace, retry, change visibility: the publisher responsible for {@code ownerDepartmentId}. */
    public ActingAs requireCanWrite(AuthPrincipal principal, UUID ownerDepartmentId) {
        UUID wid = principal.workspaceId();
        Member member = publishers.member(wid, principal.userId()).filter(Member::active)
                .orElseThrow(DocumentWritePolicy::notPublisher);
        return requirePublisher(wid, member, ownerDepartmentId);
    }

    /**
     * Create: {@code WORKSPACE} needs the workspace publisher; {@code DEPARTMENTS} the publisher of
     * {@code ownerDepartmentId}, which defaults to the caller's own department and must be one of the readers.
     * A caller with no department who names none is refused as a non-publisher.
     * Returns the resolved owner department ({@code null} for {@code WORKSPACE}).
     */
    public Creation requireCanCreate(AuthPrincipal principal, String visibility, UUID requestedOwnerDepartmentId,
                                     List<UUID> departmentIds) {
        UUID wid = principal.workspaceId();
        Member member = publishers.member(wid, principal.userId()).filter(Member::active)
                .orElseThrow(DocumentWritePolicy::notPublisher);
        if ("WORKSPACE".equals(visibility)) {
            if (requestedOwnerDepartmentId != null) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED",
                        "A workspace document has no owner department.");
            }
            return new Creation(null, requirePublisher(wid, member, null));
        }
        UUID owner = requestedOwnerDepartmentId != null ? requestedOwnerDepartmentId : member.departmentId();
        if (owner == null) {
            // No department of their own and none named: a department publisher always has a department, so this
            // caller cannot be one. Refuse as a non-publisher rather than asking them to pick a department.
            throw notPublisher();
        }
        if (departmentIds == null || !departmentIds.contains(owner)) {
            throw ownerNotInScope();
        }
        return new Creation(owner, requirePublisher(wid, member, owner));
    }

    public record Creation(UUID ownerDepartmentId, ActingAs actingAs) {
    }

    /** Delete: any ACTIVE OWNER (recall), otherwise the responsible publisher. */
    public ActingAs requireCanDelete(AuthPrincipal principal, UUID ownerDepartmentId) {
        Member member = publishers.member(principal.workspaceId(), principal.userId()).filter(Member::active)
                .orElseThrow(DocumentWritePolicy::notPublisher);
        if (member.isOwner()) {
            return ActingAs.OWNER;
        }
        return requirePublisher(principal.workspaceId(), member, ownerDepartmentId);
    }

    /** Transfer of responsibility ({@code PUT /ownership}): ACTIVE OWNER only, nothing else qualifies. */
    public void requireCanTransfer(AuthPrincipal principal) {
        boolean owner = publishers.member(principal.workspaceId(), principal.userId()).map(Member::isOwner)
                .orElse(false);
        if (!owner) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "You do not have permission to do this.");
        }
    }

    /**
     * What the caller publishes, for deciding whether a document view shows administrative fields. No locks and
     * no per-document query: load once per request and ask {@link PublisherScope#covers}.
     */
    public PublisherScope scopeOf(AuthPrincipal principal) {
        UUID wid = principal.workspaceId();
        boolean workspace = publishers.isWorkspacePublisher(wid, principal.userId());
        Set<UUID> departments = new HashSet<>(publishers.departmentsPublishedBy(wid, principal.userId()));
        return new PublisherScope(workspace, departments);
    }

    public record PublisherScope(boolean workspace, Set<UUID> departments) {
        public static final PublisherScope NONE = new PublisherScope(false, Set.of());

        /** True when the caller is the publisher responsible for a document with this owner department. */
        public boolean covers(UUID ownerDepartmentId) {
            return ownerDepartmentId == null ? workspace : departments.contains(ownerDepartmentId);
        }
    }

    /** Does anyone currently publish for this scope ({@code null} = the workspace)? Informational, no lock. */
    public boolean hasPublisherFor(UUID workspaceId, UUID ownerDepartmentId) {
        return ownerDepartmentId == null ? publishers.hasWorkspacePublisher(workspaceId)
                : publishers.hasDepartmentPublisher(workspaceId, ownerDepartmentId);
    }

    // ---- internals ------------------------------------------------------------------------------

    private ActingAs requirePublisher(UUID wid, Member member, UUID ownerDepartmentId) {
        Optional<UUID> publisher;
        if (ownerDepartmentId == null) {
            publisher = publishers.lockWorkspacePublisherShared(wid);
        } else {
            publisher = publishers.lockDepartmentPublisherShared(wid, ownerDepartmentId);
            // Second layer: a publisher who has since moved to another department no longer publishes for this one.
            if (!ownerDepartmentId.equals(member.departmentId())) {
                throw notPublisher();
            }
        }
        if (publisher.isEmpty() || !publisher.get().equals(member.userId())) {
            throw notPublisher();
        }
        return ownerDepartmentId == null ? ActingAs.WORKSPACE_PUBLISHER : ActingAs.DEPARTMENT_PUBLISHER;
    }

    static ApiException notPublisher() {
        return new ApiException(HttpStatus.FORBIDDEN, "NOT_PUBLISHER",
                "Only the publisher of this document can do this.");
    }

    static ApiException ownerNotInScope() {
        return new ApiException(HttpStatus.BAD_REQUEST, "OWNER_DEPARTMENT_NOT_IN_SCOPE",
                "The owner department must be one of the departments that can read the document.");
    }
}
