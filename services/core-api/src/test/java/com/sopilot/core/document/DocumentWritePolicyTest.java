package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.department.PublisherRepository;
import com.sopilot.core.department.PublisherRepository.Member;
import com.sopilot.core.document.DocumentWritePolicy.ActingAs;
import com.sopilot.core.document.DocumentWritePolicy.PublisherScope;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.security.WorkspaceRole;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * The write table of ADR-009 / TECH §15.3 without a database: role x publisher x scope. The token's role and
 * department are deliberately wrong in several cases, to show that only the database row counts.
 */
class DocumentWritePolicyTest {

    private final UUID wid = UUID.randomUUID();
    private final UUID deptD = UUID.randomUUID();
    private final UUID deptD2 = UUID.randomUUID();

    private PublisherRepository repo;
    private DocumentWritePolicy policy;

    @BeforeEach
    void setUp() {
        repo = mock(PublisherRepository.class);
        policy = new DocumentWritePolicy(repo);
        when(repo.lockWorkspacePublisherShared(wid)).thenReturn(Optional.empty());
        when(repo.lockDepartmentPublisherShared(org.mockito.ArgumentMatchers.eq(wid),
                org.mockito.ArgumentMatchers.any())).thenReturn(Optional.empty());
    }

    /** The token claims nothing useful on purpose: the policy must not read {@code wrole}/{@code wdept}. */
    private AuthPrincipal caller(UUID userId) {
        return new AuthPrincipal(userId, wid, WorkspaceRole.MEMBER, null);
    }

    private UUID member(String role, boolean active, UUID department) {
        UUID id = UUID.randomUUID();
        when(repo.member(wid, id)).thenReturn(Optional.of(new Member(id, role, active, department, "name")));
        return id;
    }

    private void workspacePublisher(UUID userId) {
        when(repo.lockWorkspacePublisherShared(wid)).thenReturn(Optional.of(userId));
    }

    private void departmentPublisher(UUID department, UUID userId) {
        when(repo.lockDepartmentPublisherShared(wid, department)).thenReturn(Optional.of(userId));
    }

    private static void assertNotPublisher(Runnable call) {
        assertThatThrownBy(call::run).isInstanceOfSatisfying(ApiException.class, e -> {
            assertThat(e.status()).isEqualTo(HttpStatus.FORBIDDEN);
            assertThat(e.code()).isEqualTo("NOT_PUBLISHER");
        });
    }

    // ---- write ----------------------------------------------------------------------------------

    @Test
    void theWorkspacePublisherWritesWorkspaceDocumentsEvenWithAMemberToken() {
        UUID publisher = member("MEMBER", true, null);
        workspacePublisher(publisher);

        assertThat(policy.requireCanWrite(caller(publisher), null)).isEqualTo(ActingAs.WORKSPACE_PUBLISHER);
    }

    @Test
    void ownerAndAdminWhoAreNotPublishersCannotWriteEitherKindOfDocument() {
        UUID publisher = member("MEMBER", true, deptD);
        workspacePublisher(publisher);
        departmentPublisher(deptD, publisher);
        UUID owner = member("OWNER", true, null);
        UUID admin = member("ADMIN", true, deptD);

        for (UUID who : List.of(owner, admin)) {
            assertNotPublisher(() -> policy.requireCanWrite(caller(who), null));
            assertNotPublisher(() -> policy.requireCanWrite(caller(who), deptD));
        }
    }

    @Test
    void theDepartmentPublisherWritesOnlyDocumentsOwnedByThatDepartment() {
        UUID publisher = member("MEMBER", true, deptD);
        departmentPublisher(deptD, publisher);
        UUID otherPublisher = member("MEMBER", true, deptD2);
        departmentPublisher(deptD2, otherPublisher);

        assertThat(policy.requireCanWrite(caller(publisher), deptD)).isEqualTo(ActingAs.DEPARTMENT_PUBLISHER);
        assertNotPublisher(() -> policy.requireCanWrite(caller(otherPublisher), deptD));
        assertNotPublisher(() -> policy.requireCanWrite(caller(publisher), deptD2));
        assertNotPublisher(() -> policy.requireCanWrite(caller(publisher), null));
    }

    @Test
    void theWorkspacePublisherDoesNotWriteDepartmentDocuments() {
        UUID publisher = member("MEMBER", true, deptD);
        workspacePublisher(publisher);

        assertNotPublisher(() -> policy.requireCanWrite(caller(publisher), deptD));
    }

    @Test
    void aPublisherWhoMovedToAnotherDepartmentCannotWriteEvenIfTheRowSurvived() {
        UUID mover = member("MEMBER", true, deptD2);
        departmentPublisher(deptD, mover);

        assertNotPublisher(() -> policy.requireCanWrite(caller(mover), deptD));
    }

    @Test
    void aSuspendedOrUnknownPublisherCannotWrite() {
        UUID suspended = member("MEMBER", false, null);
        workspacePublisher(suspended);
        UUID stranger = UUID.randomUUID();
        when(repo.member(wid, stranger)).thenReturn(Optional.empty());

        assertNotPublisher(() -> policy.requireCanWrite(caller(suspended), null));
        assertNotPublisher(() -> policy.requireCanWrite(caller(stranger), null));
    }

    @Test
    void aScopeWithoutPublisherCannotBeWrittenByAnyone() {
        UUID owner = member("OWNER", true, null);
        UUID someone = member("MEMBER", true, deptD);

        for (UUID who : List.of(owner, someone)) {
            assertNotPublisher(() -> policy.requireCanWrite(caller(who), deptD));
            assertNotPublisher(() -> policy.requireCanWrite(caller(who), null));
        }
    }

    // ---- create ---------------------------------------------------------------------------------

    @Test
    void creatingAWorkspaceDocumentNeedsTheWorkspacePublisherAndNoOwnerDepartment() {
        UUID publisher = member("MEMBER", true, null);
        workspacePublisher(publisher);

        var creation = policy.requireCanCreate(caller(publisher), "WORKSPACE", null, List.of());

        assertThat(creation.ownerDepartmentId()).isNull();
        assertThat(creation.actingAs()).isEqualTo(ActingAs.WORKSPACE_PUBLISHER);
        assertThatThrownBy(() -> policy.requireCanCreate(caller(publisher), "WORKSPACE", deptD, List.of()))
                .isInstanceOfSatisfying(ApiException.class,
                        e -> assertThat(e.status()).isEqualTo(HttpStatus.BAD_REQUEST));
    }

    @Test
    void theOwnerDepartmentDefaultsToTheCallersAndMustBeAmongTheReaders() {
        UUID publisher = member("MEMBER", true, deptD);
        departmentPublisher(deptD, publisher);

        var defaulted = policy.requireCanCreate(caller(publisher), "DEPARTMENTS", null, List.of(deptD, deptD2));

        assertThat(defaulted.ownerDepartmentId()).isEqualTo(deptD);
        assertThat(defaulted.actingAs()).isEqualTo(ActingAs.DEPARTMENT_PUBLISHER);
        assertThatThrownBy(() -> policy.requireCanCreate(caller(publisher), "DEPARTMENTS", null, List.of(deptD2)))
                .isInstanceOfSatisfying(ApiException.class, e -> {
                    assertThat(e.status()).isEqualTo(HttpStatus.BAD_REQUEST);
                    assertThat(e.code()).isEqualTo("OWNER_DEPARTMENT_NOT_IN_SCOPE");
                });
    }

    @Test
    void aCallerWithoutADepartmentWhoNamesNoneIsRefusedAsANonPublisher() {
        UUID noDepartment = member("MEMBER", true, null);

        assertNotPublisher(() -> policy.requireCanCreate(caller(noDepartment), "DEPARTMENTS", null, List.of(deptD)));
    }

    @Test
    void creatingForADepartmentYouDoNotPublishForIsRefused() {
        UUID publisher = member("MEMBER", true, deptD);
        departmentPublisher(deptD, publisher);
        UUID admin = member("ADMIN", true, deptD);

        assertNotPublisher(() -> policy.requireCanCreate(caller(publisher), "DEPARTMENTS", deptD2, List.of(deptD2)));
        assertNotPublisher(() -> policy.requireCanCreate(caller(admin), "DEPARTMENTS", null, List.of(deptD)));
        assertNotPublisher(() -> policy.requireCanCreate(caller(admin), "WORKSPACE", null, List.of()));
    }

    // ---- delete and transfer --------------------------------------------------------------------

    @Test
    void anActiveOwnerCanDeleteAnyDocumentEvenWhenItsDepartmentHasNoPublisher() {
        UUID owner = member("OWNER", true, null);

        assertThat(policy.requireCanDelete(caller(owner), deptD)).isEqualTo(ActingAs.OWNER);
        assertThat(policy.requireCanDelete(caller(owner), null)).isEqualTo(ActingAs.OWNER);
    }

    @Test
    void aDemotedOrSuspendedOwnerCannotRecallEvenWithAnOwnerToken() {
        UUID demoted = member("ADMIN", true, null);
        UUID suspended = member("OWNER", false, null);
        AuthPrincipal staleOwnerToken = new AuthPrincipal(demoted, wid, WorkspaceRole.OWNER, null);

        assertNotPublisher(() -> policy.requireCanDelete(staleOwnerToken, deptD));
        assertNotPublisher(() -> policy.requireCanDelete(caller(suspended), deptD));
    }

    @Test
    void deleteByThePublisherIsActingAsPublisherAndByAdminIsRefused() {
        UUID publisher = member("MEMBER", true, deptD);
        departmentPublisher(deptD, publisher);
        UUID admin = member("ADMIN", true, deptD);

        assertThat(policy.requireCanDelete(caller(publisher), deptD)).isEqualTo(ActingAs.DEPARTMENT_PUBLISHER);
        assertNotPublisher(() -> policy.requireCanDelete(caller(admin), deptD));
    }

    @Test
    void onlyAnActiveOwnerCanTransferResponsibility() {
        UUID owner = member("OWNER", true, null);
        UUID admin = member("ADMIN", true, null);
        UUID publisher = member("MEMBER", true, deptD);
        UUID suspendedOwner = member("OWNER", false, null);

        policy.requireCanTransfer(caller(owner));
        for (UUID who : List.of(admin, publisher, suspendedOwner, UUID.randomUUID())) {
            assertThatThrownBy(() -> policy.requireCanTransfer(caller(who)))
                    .isInstanceOfSatisfying(ApiException.class, e -> {
                        assertThat(e.status()).isEqualTo(HttpStatus.FORBIDDEN);
                        assertThat(e.code()).isEqualTo("FORBIDDEN");
                    });
        }
    }

    // ---- view scope -----------------------------------------------------------------------------

    @Test
    void publisherScopeCoversOnlyWhatTheCallerPublishes() {
        PublisherScope scope = new PublisherScope(false, Set.of(deptD));

        assertThat(scope.covers(deptD)).isTrue();
        assertThat(scope.covers(deptD2)).isFalse();
        assertThat(scope.covers(null)).isFalse();
        assertThat(new PublisherScope(true, Set.of()).covers(null)).isTrue();
        assertThat(PublisherScope.NONE.covers(null)).isFalse();
    }
}
