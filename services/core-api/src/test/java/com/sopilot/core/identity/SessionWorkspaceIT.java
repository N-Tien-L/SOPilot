package com.sopilot.core.identity;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.identity.RefreshTokenService.Rotation;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.security.WorkspaceRole;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** Refresh rotation, replay, membership checks, workspace switching and workspace CRUD (V2-29). */
class SessionWorkspaceIT extends ApiIT {

    private static final String ORIGIN = "http://localhost:3000";

    @Autowired RefreshTokenService refresh;

    // ---- refresh rotation -------------------------------------------------------------------------

    @Test
    void refreshExchangesTheTokenForANewPairInTheSameFamily() {
        var session = identity.loginWithSession(claims("rot"));

        Rotation next = refresh.rotate(session.refreshToken());

        assertThat(next.accepted()).isTrue();
        assertThat(next.refreshToken()).isNotEqualTo(session.refreshToken());
        AuthPrincipal principal = verifier.verify(next.access().value()).orElseThrow();
        assertThat(principal.userId()).isEqualTo(session.response().user().id());
        assertThat(principal.workspaceId()).isEqualTo(session.response().workspace().id());
        assertThat(refresh.rotate(next.refreshToken()).accepted()).isTrue();
    }

    @Test
    void replayingAnExchangedTokenRevokesTheWholeChain() {
        var session = identity.loginWithSession(claims("replay"));
        Rotation next = refresh.rotate(session.refreshToken());

        Rotation replay = refresh.rotate(session.refreshToken());

        assertThat(replay.accepted()).isFalse();
        assertThat(replay.code()).isEqualTo("UNAUTHENTICATED");
        // The legitimate successor dies with the family.
        assertThat(refresh.rotate(next.refreshToken()).accepted()).isFalse();
    }

    @Test
    void anUnknownOrMalformedTokenIsRejectedWithoutDetail() {
        Rotation rotation = refresh.rotate("not-a-real-token");

        assertThat(rotation.accepted()).isFalse();
        assertThat(rotation.status()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void anExpiredTokenIsRejected() {
        var session = identity.loginWithSession(claims("exp"));
        migrator("UPDATE core.refresh_tokens SET expires_at = now() - interval '1 minute' WHERE user_id = ?",
                session.response().user().id());

        assertThat(refresh.rotate(session.refreshToken()).accepted()).isFalse();
    }

    @Test
    void refreshReadsTheRoleFromTheDatabaseNotFromTheOldToken() {
        var session = identity.loginWithSession(claims("role"));
        UUID user = session.response().user().id();
        UUID workspace = session.response().workspace().id();
        migrator("UPDATE core.memberships SET role = 'ADMIN' WHERE user_id = ? AND workspace_id = ?", user, workspace);

        Rotation next = refresh.rotate(session.refreshToken());

        assertThat(verifier.verify(next.access().value()).orElseThrow().role()).isEqualTo(WorkspaceRole.ADMIN);
    }

    @Test
    void aSuspendedMemberCannotRefreshAndTheChainIsRevoked() {
        Actor owner = newTeamWorkspace("susp-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "susp-member");
        String token = startChain(member);
        migrator("UPDATE core.memberships SET status = 'SUSPENDED', suspended_at = now() WHERE user_id = ? "
                + "AND workspace_id = ?", member.userId(), member.workspaceId());

        Rotation rotation = refresh.rotate(token);

        assertThat(rotation.status()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(rotation.code()).isEqualTo("MEMBERSHIP_SUSPENDED");
        migrator("UPDATE core.memberships SET status = 'ACTIVE', suspended_at = NULL WHERE user_id = ?",
                member.userId());
        assertThat(refresh.rotate(token).accepted()).as("the chain stays revoked after reactivation").isFalse();
    }

    @Test
    void aMemberWhoLostTheMembershipGetsMembershipLost() {
        Actor owner = newTeamWorkspace("lost-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "lost-member");
        String token = startChain(member);
        migrator("DELETE FROM core.memberships WHERE user_id = ? AND workspace_id = ?",
                member.userId(), member.workspaceId());

        Rotation rotation = refresh.rotate(token);

        assertThat(rotation.status()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(rotation.code()).isEqualTo("MEMBERSHIP_LOST");
    }

    @Test
    void suspendingThroughTheApiEndsTheMembersSessionsImmediately() {
        Actor owner = newTeamWorkspace("api-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "api-member");
        String token = startChain(member);

        assertThat(post("/api/v1/members/" + member.userId() + "/suspend", owner, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(post("/api/v1/members/" + member.userId() + "/reactivate", owner, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);

        assertThat(refresh.rotate(token).accepted()).isFalse();
    }

    @Test
    void removingAMemberThroughTheApiEndsTheirSessions() {
        Actor owner = newTeamWorkspace("rm-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "rm-member");
        String token = startChain(member);

        assertThat(delete("/api/v1/members/" + member.userId(), owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);

        assertThat(refresh.rotate(token).accepted()).isFalse();
    }

    // ---- HTTP: cookie, Origin, logout -------------------------------------------------------------

    @Test
    void refreshOverHttpRequiresTheFrontendOriginAndRotatesTheCookie() {
        var session = devLogin("http-refresh");
        String cookie = session.cookie;

        ResponseEntity<JsonNode> noOrigin = cookiePost("/api/v1/auth/refresh", cookie, null, null);
        assertThat(noOrigin.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);

        ResponseEntity<JsonNode> wrongOrigin = cookiePost("/api/v1/auth/refresh", cookie, "http://evil.example", null);
        assertThat(wrongOrigin.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);

        ResponseEntity<JsonNode> ok = cookiePost("/api/v1/auth/refresh", cookie, ORIGIN, null);
        assertThat(ok.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(ok.getBody().path("data").path("accessToken").asText()).isNotBlank();
        String rotated = refreshCookie(ok);
        assertThat(rotated).isNotEqualTo(cookie);
        assertThat(ok.getHeaders().getFirst(HttpHeaders.SET_COOKIE)).contains("HttpOnly").contains("SameSite=Strict")
                .contains("Path=/api/v1/auth");

        // Replaying the old cookie is rejected and clears the cookie.
        ResponseEntity<JsonNode> replay = cookiePost("/api/v1/auth/refresh", cookie, ORIGIN, null);
        assertThat(replay.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(replay.getHeaders().getFirst(HttpHeaders.SET_COOKIE)).contains("Max-Age=0");
    }

    @Test
    void refreshWithoutACookieIsUnauthenticated() {
        ResponseEntity<JsonNode> response = cookiePost("/api/v1/auth/refresh", null, ORIGIN, null);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(response.getBody().path("error").path("code").asText()).isEqualTo("UNAUTHENTICATED");
    }

    @Test
    void logoutRevokesTheChainAndAlwaysAnswersNoContent() {
        var session = devLogin("http-logout");

        ResponseEntity<JsonNode> out = cookiePost("/api/v1/auth/logout", session.cookie, ORIGIN, null);
        assertThat(out.getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(out.getHeaders().getFirst(HttpHeaders.SET_COOKIE)).contains("Max-Age=0");
        assertThat(cookiePost("/api/v1/auth/refresh", session.cookie, ORIGIN, null).getStatusCode())
                .isEqualTo(HttpStatus.UNAUTHORIZED);

        assertThat(cookiePost("/api/v1/auth/logout", null, ORIGIN, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(cookiePost("/api/v1/auth/logout", session.cookie, null, null).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
    }

    // ---- workspaces -------------------------------------------------------------------------------

    @Test
    void creatingAWorkspaceMakesTheCallerItsOwnerAndReturnsTokensForIt() {
        Actor user = loginPersonal("create");

        ResponseEntity<JsonNode> created = post("/api/v1/workspaces", user, Map.of("name", "  Acme Ops  "));

        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        JsonNode data = created.getBody().path("data");
        assertThat(data.path("workspace").path("name").asText()).isEqualTo("Acme Ops");
        assertThat(data.path("workspace").path("kind").asText()).isEqualTo("TEAM");
        assertThat(data.path("workspace").path("role").asText()).isEqualTo("OWNER");
        AuthPrincipal principal = verifier.verify(data.path("accessToken").asText()).orElseThrow();
        assertThat(principal.workspaceId()).isEqualTo(UUID.fromString(data.path("workspace").path("id").asText()));
        assertThat(principal.role()).isEqualTo(WorkspaceRole.OWNER);
        assertThat(created.getHeaders().getFirst(HttpHeaders.SET_COOKIE)).startsWith("sp_refresh=");

        ResponseEntity<JsonNode> mine = get("/api/v1/workspaces", user);
        assertThat(mine.getBody().path("data")).hasSize(2);
    }

    @Test
    void workspaceNameIsValidated() {
        Actor user = loginPersonal("badname");

        assertThat(post("/api/v1/workspaces", user, Map.of("name", "   ")).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(post("/api/v1/workspaces", user, Map.of("name", "x".repeat(101))).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(post("/api/v1/workspaces", user, Map.of()).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void listingShowsOnlyMyWorkspacesWithMyRole() {
        Actor owner = newTeamWorkspace("list-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "list-member");
        Actor stranger = newTeamWorkspace("list-stranger");

        JsonNode data = get("/api/v1/workspaces", member).getBody().path("data");

        assertThat(data).hasSize(1);
        assertThat(data.get(0).path("id").asText()).isEqualTo(owner.workspaceId().toString());
        assertThat(data.get(0).path("role").asText()).isEqualTo("MEMBER");
        assertThat(data.toString()).doesNotContain(stranger.workspaceId().toString());
    }

    @Test
    void switchingWorkspaceIssuesTokensForTheTargetAndEndsTheOldChain() {
        var session = devLogin("switch");
        Actor me = new Actor(session.userId, session.workspaceId, WorkspaceRole.OWNER, session.accessToken);
        UUID team = UUID.randomUUID();
        migrator("INSERT INTO core.workspaces (id, name, kind, created_by) VALUES (?, 'Other', 'TEAM', ?)", team, me.userId());
        seedMembership(team, me.userId(), "ADMIN");

        ResponseEntity<JsonNode> switched = cookiePost("/api/v1/auth/switch-workspace", session.cookie, null,
                Map.of("workspaceId", team), me.token());

        assertThat(switched.getStatusCode()).isEqualTo(HttpStatus.OK);
        AuthPrincipal principal = verifier.verify(switched.getBody().path("data").path("accessToken").asText()).orElseThrow();
        assertThat(principal.workspaceId()).isEqualTo(team);
        assertThat(principal.role()).isEqualTo(WorkspaceRole.ADMIN);
        assertThat(refresh.rotate(refreshCookieValue(session.cookie)).accepted()).as("old chain revoked").isFalse();
        assertThat(refresh.rotate(refreshCookieValue(refreshCookie(switched))).accepted()).isTrue();
        assertThat(jdbc.queryForObject("SELECT last_active_workspace_id FROM core.users WHERE id = ?", UUID.class,
                me.userId())).isEqualTo(team);
    }

    @Test
    void switchingToAWorkspaceIAmNotAMemberOfIsNotFound() {
        var session = devLogin("nomember");
        Actor other = newTeamWorkspace("nomember-other");

        ResponseEntity<JsonNode> response = cookiePost("/api/v1/auth/switch-workspace", session.cookie, null,
                Map.of("workspaceId", other.workspaceId()), session.accessToken);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(response.getBody().path("error").path("code").asText()).isEqualTo("NOT_FOUND");
    }

    @Test
    void switchingWithoutABearerTokenIsUnauthenticated() {
        Actor other = newTeamWorkspace("nobearer");

        ResponseEntity<JsonNode> response = cookiePost("/api/v1/auth/switch-workspace", null, null,
                Map.of("workspaceId", other.workspaceId()), null);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void switchingToAWorkspaceWhereIAmSuspendedIsForbidden() {
        Actor owner = newTeamWorkspace("sw-susp-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "sw-susp-member");
        migrator("UPDATE core.memberships SET status = 'SUSPENDED', suspended_at = now() WHERE user_id = ? "
                + "AND workspace_id = ?", member.userId(), member.workspaceId());
        Actor personal = new Actor(member.userId(), member.workspaceId(), WorkspaceRole.MEMBER, member.token());

        ResponseEntity<JsonNode> response = cookiePost("/api/v1/auth/switch-workspace", null, null,
                Map.of("workspaceId", owner.workspaceId()), personal.token());

        // The suspended member's own token still verifies for up to 15 minutes; the switch itself is refused.
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(response.getBody().path("error").path("code").asText()).isEqualTo("MEMBERSHIP_SUSPENDED");
    }

    @Test
    void currentWorkspaceShowsUsageAndOnlyTheOwnerCanRename() {
        Actor owner = newTeamWorkspace("cur-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "cur-member");
        assertThat(uploadDocument(owner, "a.md", markdown("alpha")).getStatusCode().is2xxSuccessful()).isTrue();

        JsonNode current = get("/api/v1/workspaces/current", member).getBody().path("data");
        assertThat(current.path("id").asText()).isEqualTo(owner.workspaceId().toString());
        assertThat(current.path("documentCount").asLong()).isEqualTo(1);
        assertThat(current.path("bytesUsed").asLong()).isPositive();
        assertThat(current.path("role").asText()).isEqualTo("MEMBER");

        assertThat(patch("/api/v1/workspaces/current", member, Map.of("name", "Hijack")).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
        ResponseEntity<JsonNode> renamed = patch("/api/v1/workspaces/current", owner, Map.of("name", "Renamed"));
        assertThat(renamed.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(renamed.getBody().path("data").path("name").asText()).isEqualTo("Renamed");
        assertThat(patch("/api/v1/workspaces/current", owner, Map.of("name", " ")).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void managementActsOnlyOnTheTokensWorkspaceNeverOnAnotherOne() {
        Actor a = newTeamWorkspace("iso-a");
        Actor b = newTeamWorkspace("iso-b");

        patch("/api/v1/workspaces/current", a, Map.of("name", "A renamed"));

        assertThat(get("/api/v1/workspaces/current", b).getBody().path("data").path("name").asText())
                .isEqualTo("iso-b team");
    }

    @Test
    void onlyTheOwnerCanDeleteAndAPersonalWorkspaceCannotBeDeleted() {
        Actor owner = newTeamWorkspace("del-owner");
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "del-admin");
        Actor personal = loginPersonal("del-personal");

        assertThat(delete("/api/v1/workspaces/current", admin).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        ResponseEntity<JsonNode> refused = delete("/api/v1/workspaces/current", personal);
        assertThat(refused.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(refused.getBody().path("error").path("code").asText()).isEqualTo("PERSONAL_WORKSPACE");
    }

    @Test
    void deletingAWorkspaceQueuesEveryDocumentDeletionAndEndsMemberSessions() {
        Actor owner = newTeamWorkspace("wdel-owner");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "wdel-member");
        uploadDocument(owner, "one.md", markdown("one"));
        uploadDocument(owner, "two.md", markdown("two"));
        String memberToken = startChain(member);

        assertThat(delete("/api/v1/workspaces/current", owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);

        long deletions = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT count(*) FROM core.outbox_events WHERE workspace_id = ? AND event_type = 'DOCUMENT_DELETED'",
                Long.class, owner.workspaceId()));
        assertThat(deletions).isEqualTo(2);
        long live = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT count(*) FROM core.documents WHERE workspace_id = ? AND deleted_at IS NULL", Long.class,
                owner.workspaceId()));
        assertThat(live).isZero();
        assertThat(get("/api/v1/workspaces", owner).getBody().path("data").toString())
                .doesNotContain(owner.workspaceId().toString());
        assertThat(get("/api/v1/workspaces/current", owner).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        Rotation rotation = refresh.rotate(memberToken);
        assertThat(rotation.accepted()).isFalse();
        assertThat(rotation.code()).isEqualTo("MEMBERSHIP_LOST");
        assertThat(post("/api/v1/auth/switch-workspace", owner, Map.of("workspaceId", owner.workspaceId()))
                .getStatusCode()).isIn(HttpStatus.NOT_FOUND, HttpStatus.UNAUTHORIZED);
    }

    // ---- helpers ----------------------------------------------------------------------------------

    private static ExternalIdentityClaims claims(String prefix) {
        String email = email(prefix);
        return new ExternalIdentityClaims("sopilot-dev", email, email, prefix, null, null);
    }

    /** A refresh chain for an existing membership, as a login into that workspace would start it. */
    private String startChain(Actor actor) {
        return refresh.start(actor.userId(), actor.workspaceId());
    }

    private record DevSession(UUID userId, UUID workspaceId, String accessToken, String cookie) {
    }

    private DevSession devLogin(String prefix) {
        ResponseEntity<JsonNode> response = http.postForEntity("/api/v1/auth/dev-login",
                Map.of("email", email(prefix), "displayName", prefix), JsonNode.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode data = response.getBody().path("data");
        return new DevSession(UUID.fromString(data.path("user").path("id").asText()),
                UUID.fromString(data.path("workspace").path("id").asText()),
                data.path("accessToken").asText(), refreshCookie(response));
    }

    /** {@code sp_refresh=<value>} taken from the Set-Cookie header. */
    private static String refreshCookie(ResponseEntity<?> response) {
        String header = response.getHeaders().getFirst(HttpHeaders.SET_COOKIE);
        assertThat(header).startsWith("sp_refresh=");
        return header.substring(0, header.indexOf(';'));
    }

    private static String refreshCookieValue(String cookie) {
        return cookie.substring("sp_refresh=".length());
    }

    private ResponseEntity<JsonNode> cookiePost(String path, String cookie, String origin, Object body) {
        return cookiePost(path, cookie, origin, body, null);
    }

    private ResponseEntity<JsonNode> cookiePost(String path, String cookie, String origin, Object body, String bearer) {
        HttpHeaders headers = new HttpHeaders();
        if (cookie != null) {
            headers.add(HttpHeaders.COOKIE, cookie);
        }
        if (origin != null) {
            headers.add(HttpHeaders.ORIGIN, origin);
        }
        if (bearer != null) {
            headers.setBearerAuth(bearer);
        }
        if (body != null) {
            headers.setContentType(MediaType.APPLICATION_JSON);
        }
        return http.exchange(path, HttpMethod.POST, new HttpEntity<>(body, headers), JsonNode.class);
    }
}
