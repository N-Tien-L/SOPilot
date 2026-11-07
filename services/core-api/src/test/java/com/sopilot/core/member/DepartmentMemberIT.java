package com.sopilot.core.member;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** V2-23: departments, member profiles, suspend/reactivate/remove, last-owner and admin rules, {@code wdept}. */
class DepartmentMemberIT extends ApiIT {

    private UUID createDepartment(Actor actor, String name) {
        ResponseEntity<JsonNode> created = post("/api/v1/departments", actor, Map.of("name", name));
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return id(created, "id");
    }

    private AuthPrincipal claims(Actor actor) {
        return verifier.verify(actor.token()).orElseThrow();
    }

    @Test
    void departmentLifecycleAndUniqueNamePerWorkspace() {
        Actor owner = newTeamWorkspace("own");
        Actor other = newTeamWorkspace("other");

        UUID id = createDepartment(owner, "Kế toán");
        assertThat(post("/api/v1/departments", owner, Map.of("name", "  kế TOÁN ")).getStatusCode())
                .isEqualTo(HttpStatus.CONFLICT);
        // The same name in another workspace is fine.
        createDepartment(other, "Kế toán");

        ResponseEntity<JsonNode> renamed = patch("/api/v1/departments/" + id, owner, Map.of("name", "Tài chính"));
        assertThat(renamed.getBody().at("/data/name").asText()).isEqualTo("Tài chính");

        patch("/api/v1/departments/" + id, owner, Map.of("status", "ARCHIVED"));
        assertThat(get("/api/v1/departments", owner).getBody().path("data")).isEmpty();
        assertThat(get("/api/v1/departments?includeArchived=true", owner).getBody().path("data")).hasSize(1);

        assertThat(delete("/api/v1/departments/" + id, owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(get("/api/v1/departments?includeArchived=true", owner).getBody().path("data")).isEmpty();
        assertThat(get("/api/v1/departments?includeArchived=true", other).getBody().path("data")).hasSize(1);
    }

    @Test
    void membersCannotManageDepartmentsButCanListActiveOnes() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        createDepartment(owner, "Mua hàng");

        assertThat(post("/api/v1/departments", member, Map.of("name", "X")).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(get("/api/v1/departments?includeArchived=true", member).getBody().path("data")).hasSize(1);
    }

    @Test
    void deleteIsRefusedWhileMembersPendingInvitationsOrDocumentsReferenceTheDepartment() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        UUID dept = createDepartment(owner, "Kho");

        patch("/api/v1/members/" + member.userId(), owner, Map.of("departmentId", dept.toString()));
        ResponseEntity<JsonNode> blocked = delete("/api/v1/departments/" + dept, owner);
        assertThat(blocked.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(blocked.getBody().at("/error/code").asText()).isEqualTo("DEPARTMENT_IN_USE");
        assertThat(blocked.getBody().at("/error/details/members").asInt()).isEqualTo(1);

        patch("/api/v1/members/" + member.userId(), owner, java.util.Collections.singletonMap("departmentId", null));
        // A pending invitation naming the department also blocks it.
        UUID invitation = UUID.randomUUID();
        asTenant(owner, () -> jdbc.update("INSERT INTO core.invitations (id, workspace_id, email, role, department_id, "
                + "token_hash, invited_by, expires_at) VALUES (?, ?, 'new@acme.com', 'MEMBER', ?, ?, ?, now() + interval '7 days')",
                invitation, owner.workspaceId(), dept, UUID.randomUUID().toString().getBytes(), owner.userId()));
        assertThat(delete("/api/v1/departments/" + dept, owner).getBody().at("/error/details/pendingInvitations").asInt())
                .isEqualTo(1);

        // Once the invitation is revoked it is history and no longer pins the department.
        asTenant(owner, () -> jdbc.update("UPDATE core.invitations SET revoked_at = now() WHERE id = ?", invitation));
        // A document limited to the department blocks it through the RESTRICT foreign key.
        UUID document = id(uploadDocument(owner, "sop.md", markdown("sop")), "id");
        asTenant(owner, () -> jdbc.update("INSERT INTO core.document_departments (workspace_id, document_id, department_id) "
                + "VALUES (?, ?, ?)", owner.workspaceId(), document, dept));
        assertThat(delete("/api/v1/departments/" + dept, owner).getBody().at("/error/details/documents").asInt())
                .isEqualTo(1);
        assertThatThrownBy(() -> asTenant(owner, () -> jdbc.update("DELETE FROM core.departments WHERE id = ?", dept)))
                .rootCause().hasMessageContaining("violates foreign key constraint");

        asTenant(owner, () -> jdbc.update("DELETE FROM core.document_departments WHERE department_id = ?", dept));
        assertThat(delete("/api/v1/departments/" + dept, owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
    }

    @Test
    void archivedDepartmentCannotReceiveNewMembersAndProfileChangesAreValidated() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        UUID dept = createDepartment(owner, "Pháp chế");
        patch("/api/v1/departments/" + dept, owner, Map.of("status", "ARCHIVED"));

        ResponseEntity<JsonNode> archived = patch("/api/v1/members/" + member.userId(), owner,
                Map.of("departmentId", dept.toString()));
        assertThat(archived.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(archived.getBody().at("/error/code").asText()).isEqualTo("DEPARTMENT_ARCHIVED");

        assertThat(patch("/api/v1/members/" + member.userId(), owner, Map.of("role", "OWNER")).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(patch("/api/v1/members/" + member.userId(), owner,
                Map.of("departmentId", UUID.randomUUID().toString())).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void profileEditsAreUniqueByEmployeeCodeAndAuditedAndMembersSeeOnlyThemselves() {
        Actor owner = newTeamWorkspace("own");
        Actor a = addMember(owner.workspaceId(), "MEMBER", "a");
        Actor b = addMember(owner.workspaceId(), "MEMBER", "b");

        ResponseEntity<JsonNode> ok = patch("/api/v1/members/" + a.userId(), owner,
                Map.of("employeeCode", "NV-001", "jobTitle", "Kế toán", "displayName", "An"));
        assertThat(ok.getBody().at("/data/employeeCode").asText()).isEqualTo("NV-001");
        ResponseEntity<JsonNode> clash = patch("/api/v1/members/" + b.userId(), owner, Map.of("employeeCode", "NV-001"));
        assertThat(clash.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(clash.getBody().at("/error/code").asText()).isEqualTo("EMPLOYEE_CODE_TAKEN");

        assertThat(get("/api/v1/members", a).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(get("/api/v1/members/me", a).getBody().at("/data/jobTitle").asText()).isEqualTo("Kế toán");
        assertThat(get("/api/v1/members?q=nv-00", owner).getBody().path("data")).hasSize(1);

        JsonNode audit = get("/api/v1/audit-logs?action=MEMBER_PROFILE_UPDATED", owner).getBody().path("data");
        assertThat(audit).hasSize(1);
        assertThat(audit.get(0).at("/details/fields").toString()).contains("employeeCode", "jobTitle", "displayName");
        assertThat(get("/api/v1/audit-logs", a).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void departmentChangeShowsInWdeptAtTheNextTokenIssue() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        UUID first = createDepartment(owner, "Kế toán");
        UUID second = createDepartment(owner, "Mua hàng");
        assertThat(claims(member).departmentId()).isNull();

        patch("/api/v1/members/" + member.userId(), owner, Map.of("departmentId", first.toString()));
        // The token already in hand keeps its old claim until the next issue (ADR-007 §4.5) ...
        assertThat(claims(member).departmentId()).isNull();
        // ... and a new one reads it from the database.
        assertThat(claims(actorFor(member.userId(), member.workspaceId())).departmentId()).isEqualTo(first);

        patch("/api/v1/members/" + member.userId(), owner, Map.of("departmentId", second.toString()));
        assertThat(claims(actorFor(member.userId(), member.workspaceId())).departmentId()).isEqualTo(second);

        JsonNode changes = get("/api/v1/audit-logs?action=MEMBER_DEPARTMENT_CHANGED", owner).getBody().path("data");
        assertThat(changes).hasSize(2);
    }

    @Test
    void suspendedMemberGetsNoNewTokenAndCanBeReactivated() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertThat(post("/api/v1/members/" + member.userId() + "/suspend", owner, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThatThrownBy(() -> sessions.reissue(member.userId(), member.workspaceId()))
                .isInstanceOfSatisfying(ApiException.class, e -> {
                    assertThat(e.status()).isEqualTo(HttpStatus.FORBIDDEN);
                    assertThat(e.code()).isEqualTo("MEMBERSHIP_SUSPENDED");
                });
        // Suspending twice is idempotent.
        assertThat(post("/api/v1/members/" + member.userId() + "/suspend", owner, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(get("/api/v1/members?status=SUSPENDED", owner).getBody().path("data")).hasSize(1);

        post("/api/v1/members/" + member.userId() + "/reactivate", owner, null);
        assertThat(sessions.reissue(member.userId(), member.workspaceId()).value()).isNotBlank();
        assertThat(get("/api/v1/audit-logs?action=MEMBER_SUSPENDED", owner).getBody().path("data")).hasSize(1);
    }

    @Test
    void removedMemberLosesTheWorkspaceButKeepsTheGlobalAccount() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertThat(delete("/api/v1/members/" + member.userId(), owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThatThrownBy(() -> sessions.reissue(member.userId(), member.workspaceId()))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.code()).isEqualTo("MEMBERSHIP_LOST"));
        assertThat(jdbc.queryForObject("SELECT count(*) FROM core.users WHERE id = ?", Long.class, member.userId()))
                .isEqualTo(1);
    }

    @Test
    void adminCannotSuspendOrRemoveAnOwnerButCanManageMembers() {
        Actor owner = newTeamWorkspace("own");
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertThat(post("/api/v1/members/" + owner.userId() + "/suspend", admin, null).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(delete("/api/v1/members/" + owner.userId(), admin).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(post("/api/v1/members/" + member.userId() + "/suspend", admin, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(post("/api/v1/members/" + member.userId() + "/suspend", member, null).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void workspaceAlwaysKeepsOneActiveOwner() {
        Actor owner = newTeamWorkspace("own");
        for (ResponseEntity<JsonNode> r : java.util.List.of(
                post("/api/v1/members/" + owner.userId() + "/suspend", owner, null),
                delete("/api/v1/members/" + owner.userId(), owner),
                post("/api/v1/members/leave", owner, null))) {
            assertThat(r.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
            assertThat(r.getBody().at("/error/code").asText()).isEqualTo("LAST_OWNER");
        }

        // With a second active owner the first may leave; the second then cannot.
        Actor second = addMember(owner.workspaceId(), "OWNER", "own2");
        assertThat(post("/api/v1/members/leave", owner, null).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(post("/api/v1/members/leave", second, null).getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    }

    @Test
    void personalWorkspaceCannotBeLeftAndNeedsNoProfileOrDepartment() {
        Actor personal = loginPersonal("solo");

        assertThat(post("/api/v1/members/leave", personal, null).getBody().at("/error/code").asText())
                .isEqualTo("PERSONAL_WORKSPACE");
        JsonNode me = get("/api/v1/members/me", personal).getBody().path("data");
        assertThat(me.path("employeeCode").isNull()).isTrue();
        assertThat(me.path("departmentId").isNull()).isTrue();
    }

    @Test
    void tokensAreRequiredAndVerified() {
        Actor owner = newTeamWorkspace("own");

        assertThat(get("/api/v1/departments", null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        Actor forged = new Actor(owner.userId(), owner.workspaceId(), owner.role(), owner.token() + "x");
        assertThat(get("/api/v1/departments", forged).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }
}
