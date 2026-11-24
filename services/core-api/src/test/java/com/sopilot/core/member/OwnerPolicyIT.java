package com.sopilot.core.member;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.identity.RefreshTokenService;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;

import static org.assertj.core.api.Assertions.assertThat;

/** V2-30: the OWNER invariants of TECH §3.2: at least one active owner, ADMIN limits, session revocation. */
class OwnerPolicyIT extends ApiIT {

    @Autowired RefreshTokenService refresh;

    private ResponseEntity<JsonNode> setRole(Actor actor, UUID target, String role) {
        return patch("/api/v1/members/" + target, actor, Map.of("role", role));
    }

    private String roleOf(Actor viewer, UUID userId) {
        return asTenant(viewer, () -> jdbc.queryForObject(
                "SELECT role FROM core.memberships WHERE workspace_id = ? AND user_id = ?", String.class,
                viewer.workspaceId(), userId));
    }

    private long liveRefreshTokens(UUID userId, UUID workspaceId) {
        return jdbc.queryForObject("SELECT count(*) FROM core.refresh_tokens WHERE user_id = ? "
                + "AND target_workspace_id = ? AND revoked_at IS NULL", Long.class, userId, workspaceId);
    }

    private void startSession(Actor owner, Actor member) {
        asTenant(owner, () -> refresh.start(member.userId(), owner.workspaceId()));
    }

    @Test
    void adminCannotMakeAnOwnerOrTouchOne() {
        Actor owner = newTeamWorkspace("own");
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertThat(setRole(admin, member.userId(), "OWNER").getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(setRole(admin, owner.userId(), "MEMBER").getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(post("/api/v1/members/" + owner.userId() + "/suspend", admin, null).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(delete("/api/v1/members/" + owner.userId(), admin).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        // An admin may still move people between ADMIN and MEMBER.
        assertThat(setRole(admin, member.userId(), "ADMIN").getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(roleOf(owner, member.userId())).isEqualTo("ADMIN");
        assertThat(roleOf(owner, owner.userId())).isEqualTo("OWNER");
    }

    @Test
    void membersCannotChangeRoles() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertThat(setRole(member, member.userId(), "OWNER").getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void ownerPromotesAndDemotesAndEveryChangeEndsTheMembersSessions() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        startSession(owner, member);
        assertThat(liveRefreshTokens(member.userId(), owner.workspaceId())).isEqualTo(1);

        ResponseEntity<JsonNode> promoted = setRole(owner, member.userId(), "OWNER");

        assertThat(promoted.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(promoted.getBody().at("/data/role").asText()).isEqualTo("OWNER");
        assertThat(liveRefreshTokens(member.userId(), owner.workspaceId())).isZero();
        startSession(owner, member);
        assertThat(setRole(owner, member.userId(), "ADMIN").getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(liveRefreshTokens(member.userId(), owner.workspaceId())).isZero();
        assertThat(get("/api/v1/audit-logs?action=MEMBER_ROLE_CHANGED", owner).getBody().path("data")).hasSize(2);
        // Setting the role a member already has changes nothing and ends no session.
        startSession(owner, member);
        assertThat(setRole(owner, member.userId(), "ADMIN").getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(liveRefreshTokens(member.userId(), owner.workspaceId())).isEqualTo(1);
    }

    @Test
    void theLastOwnerCannotLeaveBeDemotedSuspendedOrRemoved() {
        Actor owner = newTeamWorkspace("own");

        ResponseEntity<JsonNode> demote = setRole(owner, owner.userId(), "ADMIN");
        assertThat(demote.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(demote.getBody().at("/error/code").asText()).isEqualTo("LAST_OWNER");
        assertThat(post("/api/v1/members/leave", owner, null).getBody().at("/error/code").asText())
                .isEqualTo("LAST_OWNER");
        assertThat(post("/api/v1/members/" + owner.userId() + "/suspend", owner, null).getStatusCode())
                .isEqualTo(HttpStatus.CONFLICT);
        assertThat(delete("/api/v1/members/" + owner.userId(), owner).getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(roleOf(owner, owner.userId())).isEqualTo("OWNER");
    }

    @Test
    void anOwnerMayStepDownWhenAnotherOwnerRemains() {
        Actor owner = newTeamWorkspace("own");
        Actor second = addMember(owner.workspaceId(), "OWNER", "own2");

        assertThat(setRole(owner, owner.userId(), "MEMBER").getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(roleOf(second, owner.userId())).isEqualTo("MEMBER");
        assertThat(setRole(second, second.userId(), "MEMBER").getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    }

    @Test
    void twoOwnersLeavingAtTheSameTimeLeaveOne() {
        Actor first = newTeamWorkspace("own");
        Actor second = addMember(first.workspaceId(), "OWNER", "own2");
        CountDownLatch go = new CountDownLatch(1);

        List<CompletableFuture<HttpStatus>> calls = List.of(first, second).stream()
                .map(a -> CompletableFuture.supplyAsync(() -> {
                    try {
                        go.await();
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                    return HttpStatus.valueOf(post("/api/v1/members/leave", a, null).getStatusCode().value());
                })).toList();
        go.countDown();
        List<HttpStatus> statuses = calls.stream().map(CompletableFuture::join).toList();

        assertThat(statuses).containsExactlyInAnyOrder(HttpStatus.NO_CONTENT, HttpStatus.CONFLICT);
        long owners = asTenant(first, () -> jdbc.queryForObject("SELECT count(*) FROM core.memberships "
                + "WHERE workspace_id = ? AND role = 'OWNER' AND status = 'ACTIVE'", Long.class, first.workspaceId()));
        assertThat(owners).isEqualTo(1);
    }

    @Test
    void anOwnerDemotedSinceSigningInCannotKeepActingAsOwner() {
        Actor owner = newTeamWorkspace("own");
        Actor second = addMember(owner.workspaceId(), "OWNER", "own2");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        assertThat(setRole(owner, second.userId(), "ADMIN").getStatusCode()).isEqualTo(HttpStatus.OK);

        // `second` still holds a token that says OWNER.
        assertThat(setRole(second, member.userId(), "OWNER").getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(setRole(second, owner.userId(), "MEMBER").getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(roleOf(owner, owner.userId())).isEqualTo("OWNER");
        assertThat(roleOf(owner, member.userId())).isEqualTo("MEMBER");
    }

    @Test
    void roleChangesStayInsideTheCallersWorkspace() {
        Actor a = newTeamWorkspace("a");
        Actor b = newTeamWorkspace("b");

        assertThat(setRole(a, b.userId(), "ADMIN").getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(roleOf(b, b.userId())).isEqualTo("OWNER");
    }

    @Test
    void anUnknownRoleIsRejected() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertThat(setRole(owner, member.userId(), "SUPERUSER").getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(patch("/api/v1/members/" + member.userId(), owner, Collections.singletonMap("role", null))
                .getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }
}
