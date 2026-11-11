package com.sopilot.core.member;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.identity.ExternalIdentityClaims;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.security.WorkspaceRole;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;

import static org.assertj.core.api.Assertions.assertThat;

/** V2-30: invitation links, acceptance rules, profile carried by the invitation, idempotence and races. */
class InvitationIT extends ApiIT {

    /** A signed-in user with a known email (the invitation is matched on it). */
    private record Invitee(Actor actor, String email) {
    }

    private Invitee invitee(String prefix) {
        String email = email(prefix);
        LoginResponse login = identity.login(new ExternalIdentityClaims("sopilot-dev", email, email, prefix, null, null));
        return new Invitee(new Actor(login.user().id(), login.workspace().id(), WorkspaceRole.OWNER,
                login.accessToken()), email);
    }

    private ResponseEntity<JsonNode> invite(Actor inviter, String email, Map<String, Object> extra) {
        Map<String, Object> body = new java.util.HashMap<>(extra);
        body.put("email", email);
        body.putIfAbsent("role", "MEMBER");
        return post("/api/v1/invitations", inviter, body);
    }

    private static String tokenOf(ResponseEntity<JsonNode> created) {
        String url = created.getBody().at("/data/inviteUrl").asText();
        assertThat(url).contains("/invite#token=");
        return url.substring(url.indexOf("#token=") + "#token=".length());
    }

    private ResponseEntity<JsonNode> acceptToken(Invitee who, String token) {
        return post("/api/v1/invitations/accept", who.actor(), Map.of("invitationToken", token));
    }

    private UUID department(Actor owner, String name) {
        return id(post("/api/v1/departments", owner, Map.of("name", name)), "id");
    }

    private long membershipCount(UUID workspaceId, UUID userId) {
        return asTenant(new Actor(userId, workspaceId, WorkspaceRole.MEMBER, null), () -> jdbc.queryForObject(
                "SELECT count(*) FROM core.memberships WHERE workspace_id = ? AND user_id = ?", Long.class,
                workspaceId, userId));
    }

    @Test
    void theLinkIsShownOnceAndStoredOnlyAsAHash() {
        Actor owner = newTeamWorkspace("own");

        ResponseEntity<JsonNode> created = invite(owner, "Binh@Acme.com", Map.of());

        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        String token = tokenOf(created);
        assertThat(token).hasSizeGreaterThanOrEqualTo(43);
        JsonNode listed = get("/api/v1/invitations", owner).getBody().path("data");
        assertThat(listed).hasSize(1);
        assertThat(listed.get(0).path("email").asText()).isEqualTo("binh@acme.com");
        assertThat(listed.get(0).toString()).doesNotContain(token).doesNotContain("inviteUrl");
        byte[] stored = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT token_hash FROM core.invitations WHERE workspace_id = ?", byte[].class, owner.workspaceId()));
        assertThat(stored).hasSize(32).isNotEqualTo(token.getBytes());
        long days = asTenant(owner, () -> jdbc.queryForObject("SELECT round(extract(epoch FROM (expires_at - created_at)) "
                + "/ 86400)::bigint FROM core.invitations WHERE workspace_id = ?", Long.class, owner.workspaceId()));
        assertThat(days).isEqualTo(7);
    }

    @Test
    void onlyManagersInviteAndNeverStraightToOwner() {
        Actor owner = newTeamWorkspace("own");
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertThat(invite(member, email("x"), Map.of()).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(get("/api/v1/invitations", member).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(invite(admin, email("y"), Map.of()).getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(invite(owner, email("z"), Map.of("role", "OWNER")).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(invite(owner, "not-an-email", Map.of()).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void acceptingAppliesTheInvitedProfileAndTheTokenCarriesTheDepartment() {
        Actor owner = newTeamWorkspace("own");
        UUID dept = department(owner, "Kế toán");
        Invitee binh = invitee("binh");

        String token = tokenOf(invite(owner, binh.email(), Map.of("role", "ADMIN", "displayName", "Bình",
                "employeeCode", "NV-012", "jobTitle", "Kế toán trưởng", "departmentId", dept.toString())));
        ResponseEntity<JsonNode> accepted = acceptToken(binh, token);

        assertThat(accepted.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(accepted.getHeaders().getFirst("Set-Cookie")).contains("sp_refresh=");
        assertThat(id(accepted, "workspace", "id")).isEqualTo(owner.workspaceId());
        assertThat(accepted.getBody().at("/data/workspace/role").asText()).isEqualTo("ADMIN");
        AuthPrincipal claims = verifier.verify(accepted.getBody().at("/data/accessToken").asText()).orElseThrow();
        assertThat(claims.workspaceId()).isEqualTo(owner.workspaceId());
        assertThat(claims.departmentId()).isEqualTo(dept);
        Actor joined = new Actor(binh.actor().userId(), owner.workspaceId(), WorkspaceRole.ADMIN,
                accepted.getBody().at("/data/accessToken").asText());
        JsonNode me = get("/api/v1/members/me", joined).getBody().path("data");
        assertThat(me.path("displayName").asText()).isEqualTo("Bình");
        assertThat(me.path("employeeCode").asText()).isEqualTo("NV-012");
        assertThat(me.path("jobTitle").asText()).isEqualTo("Kế toán trưởng");
        assertThat(get("/api/v1/invitations", owner).getBody().path("data")).isEmpty();
        assertThat(get("/api/v1/audit-logs?action=INVITATION_ACCEPTED", owner).getBody().path("data")).hasSize(1);
    }

    @Test
    void aSecondAcceptByTheSameUserIsANoOpAndAnotherUserIsRefused() {
        Actor owner = newTeamWorkspace("own");
        Invitee binh = invitee("binh");
        String token = tokenOf(invite(owner, binh.email(), Map.of()));

        assertThat(acceptToken(binh, token).getStatusCode()).isEqualTo(HttpStatus.OK);
        ResponseEntity<JsonNode> again = acceptToken(binh, token);

        assertThat(again.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(membershipCount(owner.workspaceId(), binh.actor().userId())).isEqualTo(1);
        ResponseEntity<JsonNode> other = acceptToken(invitee("other"), token);
        // Once redeemed the link is dead for everyone except the user who redeemed it.
        assertThat(other.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(other.getBody().at("/error/code").asText()).isEqualTo("INVITATION_ALREADY_USED");
        assertThat(get("/api/v1/audit-logs?action=INVITATION_ACCEPTED", owner).getBody().path("data")).hasSize(1);
    }

    @Test
    void aLinkForAnotherEmailIsRefusedAndStaysUsable() {
        Actor owner = newTeamWorkspace("own");
        Invitee binh = invitee("binh");
        String token = tokenOf(invite(owner, binh.email(), Map.of()));

        ResponseEntity<JsonNode> wrong = acceptToken(invitee("intruder"), token);

        assertThat(wrong.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(wrong.getBody().at("/error/code").asText()).isEqualTo("INVITATION_EMAIL_MISMATCH");
        assertThat(acceptToken(binh, token).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void expiredRevokedAndUnknownLinksAreRefused() {
        Actor owner = newTeamWorkspace("own");
        Invitee a = invitee("a");
        Invitee b = invitee("b");
        String expired = tokenOf(invite(owner, a.email(), Map.of()));
        migrator("UPDATE core.invitations SET expires_at = now() - interval '1 second' WHERE email = ?", a.email());
        ResponseEntity<JsonNode> revokedInvite = invite(owner, b.email(), Map.of());
        String revoked = tokenOf(revokedInvite);

        assertThat(delete("/api/v1/invitations/" + id(revokedInvite, "id"), owner).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);

        ResponseEntity<JsonNode> late = acceptToken(a, expired);
        assertThat(late.getStatusCode()).isEqualTo(HttpStatus.GONE);
        assertThat(late.getBody().at("/error/code").asText()).isEqualTo("INVITATION_EXPIRED");
        ResponseEntity<JsonNode> gone = acceptToken(b, revoked);
        assertThat(gone.getStatusCode()).isEqualTo(HttpStatus.GONE);
        assertThat(gone.getBody().at("/error/code").asText()).isEqualTo("INVITATION_REVOKED");
        assertThat(acceptToken(a, "no-such-token").getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(membershipCount(owner.workspaceId(), a.actor().userId())).isZero();
        assertThat(membershipCount(owner.workspaceId(), b.actor().userId())).isZero();
    }

    @Test
    void anInviteeSeesTheirPendingInvitationAtLoginAndCanAcceptItById() {
        Actor owner = newTeamWorkspace("own");
        String email = email("lost");
        invite(owner, email, Map.of("role", "ADMIN"));

        LoginResponse login = identity.login(new ExternalIdentityClaims("sopilot-dev", email, email, "lost", null, null));

        assertThat(login.pendingInvitations()).hasSize(1);
        assertThat(login.pendingInvitations().get(0).role()).isEqualTo("ADMIN");
        Actor lost = new Actor(login.user().id(), login.workspace().id(), WorkspaceRole.OWNER, login.accessToken());
        UUID invitationId = login.pendingInvitations().get(0).id();
        // A stranger cannot redeem someone else's invitation by id, and cannot tell it exists.
        assertThat(post("/api/v1/invitations/accept", invitee("stranger").actor(),
                Map.of("invitationId", invitationId.toString())).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);

        ResponseEntity<JsonNode> accepted = post("/api/v1/invitations/accept", lost,
                Map.of("invitationId", invitationId.toString()));
        assertThat(accepted.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(id(accepted, "workspace", "id")).isEqualTo(owner.workspaceId());
        assertThat(post("/api/v1/invitations/accept", lost, Map.of()).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void concurrentAcceptsOfOneLinkCreateOneMembership() throws Exception {
        Actor owner = newTeamWorkspace("own");
        Invitee binh = invitee("binh");
        String token = tokenOf(invite(owner, binh.email(), Map.of()));
        int callers = 6;
        CountDownLatch go = new CountDownLatch(1);

        List<CompletableFuture<HttpStatus>> calls = new java.util.ArrayList<>();
        for (int i = 0; i < callers; i++) {
            calls.add(CompletableFuture.supplyAsync(() -> {
                try {
                    go.await();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                return HttpStatus.valueOf(acceptToken(binh, token).getStatusCode().value());
            }));
        }
        go.countDown();
        List<HttpStatus> statuses = calls.stream().map(CompletableFuture::join).toList();

        // Every caller is the invitee, so all succeed (one creates, the rest replay) and nothing is duplicated.
        assertThat(statuses).containsOnly(HttpStatus.OK);
        assertThat(membershipCount(owner.workspaceId(), binh.actor().userId())).isEqualTo(1);
        assertThat(get("/api/v1/audit-logs?action=INVITATION_ACCEPTED", owner).getBody().path("data")).hasSize(1);
    }

    @Test
    void invitationRulesRejectBadTargets() {
        Actor owner = newTeamWorkspace("own");
        UUID archived = department(owner, "Cũ");
        patch("/api/v1/departments/" + archived, owner, Map.of("status", "ARCHIVED"));
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        String memberEmail = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT email FROM core.memberships WHERE workspace_id = ? AND user_id = ?", String.class,
                owner.workspaceId(), member.userId()));
        patch("/api/v1/members/" + member.userId(), owner, Map.of("employeeCode", "NV-001"));

        ResponseEntity<JsonNode> toArchived = invite(owner, email("a"), Map.of("departmentId", archived.toString()));
        assertThat(toArchived.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(toArchived.getBody().at("/error/code").asText()).isEqualTo("DEPARTMENT_ARCHIVED");
        assertThat(invite(owner, email("b"), Map.of("departmentId", UUID.randomUUID().toString())).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(invite(owner, memberEmail, Map.of()).getBody().at("/error/code").asText()).isEqualTo("ALREADY_MEMBER");
        assertThat(invite(owner, email("c"), Map.of("employeeCode", "NV-001")).getBody().at("/error/code").asText())
                .isEqualTo("EMPLOYEE_CODE_TAKEN");

        String same = email("dup");
        assertThat(invite(owner, same, Map.of("employeeCode", "NV-777")).getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(invite(owner, same, Map.of()).getBody().at("/error/code").asText()).isEqualTo("INVITATION_PENDING");
        assertThat(invite(owner, email("d"), Map.of("employeeCode", "NV-777")).getBody().at("/error/code").asText())
                .isEqualTo("EMPLOYEE_CODE_TAKEN");
    }

    @Test
    void anExpiredInvitationDoesNotBlockInvitingTheSameEmailAgain() {
        Actor owner = newTeamWorkspace("own");
        String email = email("again");
        invite(owner, email, Map.of());
        migrator("UPDATE core.invitations SET expires_at = now() - interval '1 second' WHERE email = ?", email);

        assertThat(invite(owner, email, Map.of()).getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(get("/api/v1/invitations", owner).getBody().path("data")).hasSize(1);
    }

    @Test
    void aDepartmentArchivedAfterInvitingIsDroppedButTheMemberStillJoins() {
        Actor owner = newTeamWorkspace("own");
        UUID dept = department(owner, "Kho");
        Invitee binh = invitee("binh");
        String token = tokenOf(invite(owner, binh.email(), Map.of("departmentId", dept.toString())));
        patch("/api/v1/departments/" + dept, owner, Map.of("status", "ARCHIVED"));

        ResponseEntity<JsonNode> accepted = acceptToken(binh, token);

        assertThat(accepted.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(verifier.verify(accepted.getBody().at("/data/accessToken").asText()).orElseThrow().departmentId())
                .isNull();
    }

    @Test
    void revokingIsIdempotentScopedToTheWorkspaceAndRefusedOnceUsed() {
        Actor owner = newTeamWorkspace("own");
        Actor other = newTeamWorkspace("other");
        Invitee binh = invitee("binh");
        ResponseEntity<JsonNode> created = invite(owner, binh.email(), Map.of());
        UUID id = id(created, "id");

        assertThat(delete("/api/v1/invitations/" + id, other).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(delete("/api/v1/invitations/" + id, owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(delete("/api/v1/invitations/" + id, owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);

        String token2 = tokenOf(invite(owner, binh.email(), Map.of()));
        acceptToken(binh, token2);
        UUID used = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT id FROM core.invitations WHERE workspace_id = ? AND accepted_at IS NOT NULL", UUID.class,
                owner.workspaceId()));
        assertThat(delete("/api/v1/invitations/" + used, owner).getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(get("/api/v1/invitations", other).getBody().path("data")).isEmpty();
    }
}
