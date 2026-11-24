package com.sopilot.core.tenancy;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.identity.RefreshTokenService;
import com.sopilot.core.identity.RefreshTokenService.Rotation;
import com.sopilot.core.outbox.OutboxEvent;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * V2-26 / FR-29, core-api half: inside ONE workspace, a document limited to departments is invisible to
 * everyone outside them (ADR-007 §4.4, TECH-V2-core-api §5.6). Kept apart from the FR-19 classes
 * ({@code TenantIsolation*IT}) so a failure names the layer that broke. Reads are tested for every cell of the
 * matrix; for writes only "a MEMBER is refused" is asserted (the full write matrix is {@code DocumentPublisherIT}).
 *
 * <p>Every document has its own title and body secret. A "cannot read" check looks for the title, the secret and
 * the document id in the whole response, not just at a smaller count. The ai-service half is
 * {@code services/ai-service/tests/integration/test_department_authorization.py}.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class DepartmentAuthorizationIT extends ApiIT {

    private static final String WS = "WS";
    private static final String A = "A";
    private static final String AB = "AB";

    @Autowired RefreshTokenService refresh;

    /** One workspace: departments A and B, five people, three documents. Read-only tests share a single copy. */
    private record World(Actor owner, Actor admin, Actor memberA, Actor memberB, Actor memberNoDept,
                         UUID deptA, UUID deptB, Map<String, Doc> docs) {
        Actor actor(String who) {
            return switch (who) {
                case "OWNER" -> owner;
                case "ADMIN" -> admin;
                case "MEMBER_A" -> memberA;
                case "MEMBER_B" -> memberB;
                case "MEMBER_NO_DEPT" -> memberNoDept;
                default -> throw new IllegalArgumentException(who);
            };
        }
    }

    private record Doc(UUID id, String title, String secret) {
    }

    private World shared;

    private World shared() {
        if (shared == null) {
            shared = buildWorld();
        }
        return shared;
    }

    // ---- fixture ----------------------------------------------------------------------------------

    private World buildWorld() {
        Actor owner = newTeamWorkspace("fr29-own");
        UUID wid = owner.workspaceId();
        UUID deptA = createDepartment(owner, "Dept A " + UUID.randomUUID());
        UUID deptB = createDepartment(owner, "Dept B " + UUID.randomUUID());
        Actor admin = addMember(wid, "ADMIN", "fr29-adm");
        Actor memberA = inDepartment(owner, addMember(wid, "MEMBER", "fr29-a"), deptA);
        Actor memberB = inDepartment(owner, addMember(wid, "MEMBER", "fr29-b"), deptB);
        Actor memberNoDept = addMember(wid, "MEMBER", "fr29-none");
        // ADR-009: documents are written by publishers. The workspace publisher (the owner, seeded as at creation)
        // uploads the WORKSPACE document; a separate department-A publisher uploads the two departmental ones, so
        // none of the five matrix actors can write and "a MEMBER is refused" stays meaningful.
        Actor publisherA = inDepartment(owner, addMember(wid, "MEMBER", "fr29-pub"), deptA);
        seedDepartmentPublisher(wid, deptA, publisherA.userId());
        Map<String, Doc> docs = Map.of(
                WS, uploadSecret(owner, "WS", "SECRET_WS_5521", "WORKSPACE"),
                A, uploadSecret(publisherA, "A", "SECRET_A_8834", "DEPARTMENTS", deptA),
                AB, uploadSecret(publisherA, "AB", "SECRET_AB_1907", "DEPARTMENTS", deptA, deptB));
        return new World(owner, admin, memberA, memberB, memberNoDept, deptA, deptB, docs);
    }

    private UUID createDepartment(Actor actor, String name) {
        ResponseEntity<JsonNode> created = post("/api/v1/departments", actor, Map.of("name", name));
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return id(created, "id");
    }

    /** Moves the member to the department and returns a token issued after the move (carries the new wdept). */
    private Actor inDepartment(Actor owner, Actor member, UUID department) {
        ResponseEntity<JsonNode> moved = patch("/api/v1/members/" + member.userId(), owner,
                Map.of("departmentId", department.toString()));
        assertThat(moved.getStatusCode()).isEqualTo(HttpStatus.OK);
        return actorFor(member.userId(), member.workspaceId());
    }

    private Doc uploadSecret(Actor owner, String label, String secret, String visibility, UUID... departments) {
        String title = "FR29-title-" + label + "-" + UUID.randomUUID().toString().substring(0, 8);
        byte[] body = ("# " + title + "\n\n" + secret + " " + UUID.randomUUID() + "\n").getBytes(StandardCharsets.UTF_8);
        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("title", title);
        params.add("visibility", visibility);
        for (UUID d : departments) {
            params.add("departmentIds", d.toString());
        }
        ResponseEntity<JsonNode> created = upload("/api/v1/documents", owner, label + ".md", body, params);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return new Doc(id(created, "id"), title, secret);
    }

    // ---- matrix expectations ----------------------------------------------------------------------

    /** ADR-007 §4.4, the three "read" rows. */
    private static boolean canRead(String who, String doc) {
        return switch (who) {
            case "OWNER", "ADMIN" -> true;
            case "MEMBER_A" -> true;
            case "MEMBER_B" -> !doc.equals(A);
            case "MEMBER_NO_DEPT" -> doc.equals(WS);
            default -> throw new IllegalArgumentException(who);
        };
    }

    static Stream<Arguments> cells() {
        return Stream.of("OWNER", "ADMIN", "MEMBER_A", "MEMBER_B", "MEMBER_NO_DEPT")
                .flatMap(who -> Stream.of(WS, A, AB).map(doc -> Arguments.of(who, doc)));
    }

    /** The body must not mention a document the caller may not read: id, title or secret. */
    private void assertNothingLeaksAbout(Doc forbidden, ResponseEntity<JsonNode> response) {
        String text = String.valueOf(response.getBody());
        assertThat(text).doesNotContain(forbidden.title(), forbidden.secret(), forbidden.id().toString());
    }

    // ---- the read matrix: one test per channel, one invocation per cell ---------------------------------

    @ParameterizedTest(name = "detail: {0} x {1}")
    @MethodSource("cells")
    void detailFollowsTheMatrix(String who, String doc) {
        World w = shared();
        Doc target = w.docs().get(doc);

        ResponseEntity<JsonNode> response = get("/api/v1/documents/" + target.id(), w.actor(who));

        if (canRead(who, doc)) {
            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
            assertThat(response.getBody().at("/data/title").asText()).isEqualTo(target.title());
        } else {
            assertThat(response.getStatusCode()).as("never 403: existence must not leak").isEqualTo(HttpStatus.NOT_FOUND);
            assertNothingLeaksAbout(target, response);
        }
    }

    @ParameterizedTest(name = "download-url: {0} x {1}")
    @MethodSource("cells")
    void downloadUrlFollowsTheMatrix(String who, String doc) {
        World w = shared();
        Doc target = w.docs().get(doc);

        ResponseEntity<JsonNode> response = get("/api/v1/documents/" + target.id() + "/download-url", w.actor(who));

        if (canRead(who, doc)) {
            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
            assertThat(response.getBody().at("/data/url").asText()).isNotBlank();
        } else {
            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
            assertThat(response.getBody().path("data").isMissingNode() || response.getBody().path("data").isNull())
                    .as("no URL in the body").isTrue();
            assertNothingLeaksAbout(target, response);
        }
    }

    @ParameterizedTest(name = "list: {0} x {1}")
    @MethodSource("cells")
    void listFollowsTheMatrix(String who, String doc) {
        World w = shared();
        Doc target = w.docs().get(doc);

        ResponseEntity<JsonNode> response = get("/api/v1/documents?limit=100", w.actor(who));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        if (canRead(who, doc)) {
            assertThat(idsOf(response)).contains(target.id().toString());
            assertThat(String.valueOf(response.getBody())).contains(target.title());
        } else {
            assertThat(idsOf(response)).doesNotContain(target.id().toString());
            assertNothingLeaksAbout(target, response);
        }
    }

    @ParameterizedTest(name = "search ?q=: {0} x {1}")
    @MethodSource("cells")
    void searchFollowsTheMatrix(String who, String doc) {
        World w = shared();
        Doc target = w.docs().get(doc);

        ResponseEntity<JsonNode> response = get("/api/v1/documents?limit=100&q=" + target.title(),
                w.actor(who));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        if (canRead(who, doc)) {
            assertThat(idsOf(response)).containsExactly(target.id().toString());
        } else {
            assertThat(response.getBody().path("data")).as("searching the exact title finds nothing").isEmpty();
            assertNothingLeaksAbout(target, response);
        }
    }

    @ParameterizedTest(name = "list and broad search return exactly the readable set: {0}")
    @MethodSource("actors")
    void listAndBroadSearchReturnExactlyTheReadableSet(String who) {
        World w = shared();
        Set<String> expected = Stream.of(WS, A, AB).filter(d -> canRead(who, d))
                .map(d -> w.docs().get(d).id().toString()).collect(java.util.stream.Collectors.toSet());

        // "FR29-title" is a prefix every document title shares, so the search would match all three.
        for (String path : List.of("/api/v1/documents?limit=100", "/api/v1/documents?limit=100&q=FR29-title")) {
            ResponseEntity<JsonNode> response = get(path, w.actor(who));
            assertThat(idsOf(response)).as(path).containsExactlyInAnyOrderElementsOf(expected);
        }
    }

    static Stream<String> actors() {
        return Stream.of("OWNER", "ADMIN", "MEMBER_A", "MEMBER_B", "MEMBER_NO_DEPT");
    }

    // ---- write rows: a MEMBER is refused (only that, see the scope note on the class) --------------------

    @ParameterizedTest(name = "a MEMBER cannot write: {0} x {1}")
    @MethodSource("memberCells")
    void aMemberIsRefusedOnEveryWriteEndpointAndNothingChanges(String who, String doc) {
        World w = shared();
        Doc target = w.docs().get(doc);
        Actor member = w.actor(who);
        String path = "/api/v1/documents/" + target.id();

        List<ResponseEntity<JsonNode>> attempts = List.of(
                patch(path, member, Map.of("title", "hijacked")),
                put(path + "/visibility", member, Map.of("visibility", "WORKSPACE", "departmentIds", List.of())),
                delete(path, member),
                post(path + "/retry", member, null));

        for (ResponseEntity<JsonNode> attempt : attempts) {
            // A readable document is 403 (not its publisher); one the member cannot read is 404, as for a random id
            // (TECH §15.3): the refusal says nothing about the existence of a document outside the member's scope.
            assertThat(attempt.getStatusCode()).isEqualTo(canRead(who, doc) ? HttpStatus.FORBIDDEN : HttpStatus.NOT_FOUND);
            assertNothingLeaksAbout(target, attempt);
        }
        ResponseEntity<JsonNode> still = get(path, w.owner());
        assertThat(still.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(still.getBody().at("/data/title").asText()).isEqualTo(target.title());
        assertThat(still.getBody().at("/data/visibility").asText()).isEqualTo(WS.equals(doc) ? "WORKSPACE" : "DEPARTMENTS");
    }

    static Stream<Arguments> memberCells() {
        return Stream.of("MEMBER_A", "MEMBER_B", "MEMBER_NO_DEPT")
                .flatMap(who -> Stream.of(WS, A, AB).map(doc -> Arguments.of(who, doc)));
    }

    @Test
    void aMemberUploadingIsRefusedAndTheRefusalIsTheSameForAnUnknownId() {
        World w = shared();

        assertThat(uploadDocument(w.memberNoDept(), "nope.md", markdown("nope")).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(delete("/api/v1/documents/" + UUID.randomUUID(), w.memberA()).getStatusCode())
                .as("a random id and a real id are indistinguishable to a MEMBER")
                .isEqualTo(delete("/api/v1/documents/" + w.docs().get(A).id(), w.memberNoDept()).getStatusCode());
    }

    // ---- change cases -----------------------------------------------------------------------------

    @Test
    void movingAMemberFromAToBTakesEffectAtTheNextRefreshAndTheOldTokenKeepsItsRightsUntilItExpires() {
        World w = buildWorld();
        Actor member = w.memberA();
        String refreshToken = refresh.start(member.userId(), member.workspaceId());
        UUID aOnly = w.docs().get(A).id();
        UUID aAndB = w.docs().get(AB).id();
        assertThat(get("/api/v1/documents/" + aOnly, member).getStatusCode()).isEqualTo(HttpStatus.OK);

        ResponseEntity<JsonNode> moved = patch("/api/v1/members/" + member.userId(), w.owner(),
                Map.of("departmentId", w.deptB().toString()));
        assertThat(moved.getStatusCode()).isEqualTo(HttpStatus.OK);

        // Before the refresh: the token still says wdept = A. This is the documented window (ADR-007 §4.5).
        assertThat(get("/api/v1/documents/" + aOnly, member).getStatusCode())
                .as("old token, A-only document: still readable until the token expires")
                .isEqualTo(HttpStatus.OK);
        assertThat(lifetimeSeconds(member.token())).as("the window is at most one access-token life")
                .isLessThanOrEqualTo(15 * 60);

        Rotation rotation = refresh.rotate(refreshToken);
        assertThat(rotation.accepted()).isTrue();
        Actor refreshed = new Actor(member.userId(), member.workspaceId(), member.role(), rotation.access().value());
        assertThat(verifier.verify(refreshed.token()).orElseThrow().departmentId()).isEqualTo(w.deptB());

        assertThat(get("/api/v1/documents/" + aOnly, refreshed).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertNothingLeaksAbout(w.docs().get(A), get("/api/v1/documents?limit=100", refreshed));
        assertThat(get("/api/v1/documents/" + aAndB, refreshed).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void aSuspendedMembersRefreshIsRejectedWithMembershipSuspendedAndTheChainIsRevoked() {
        World w = buildWorld();
        Actor member = w.memberA();
        String refreshToken = refresh.start(member.userId(), member.workspaceId());
        // Direct SQL: the status flips without the eager chain revocation that the API does, so the refresh itself
        // is what notices (V2-29 behaviour; SessionWorkspaceIT covers the same state).
        migrator("UPDATE core.memberships SET status = 'SUSPENDED', suspended_at = now() WHERE user_id = ? "
                + "AND workspace_id = ?", member.userId(), member.workspaceId());

        Rotation rotation = refresh.rotate(refreshToken);

        assertThat(rotation.accepted()).isFalse();
        assertThat(rotation.status()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(rotation.code()).isEqualTo("MEMBERSHIP_SUSPENDED");
        migrator("UPDATE core.memberships SET status = 'ACTIVE', suspended_at = NULL WHERE user_id = ?", member.userId());
        assertThat(refresh.rotate(refreshToken).accepted()).as("the family stays revoked after reactivation").isFalse();
    }

    @Test
    void suspendingThroughTheApiKillsTheRefreshChainButTheAccessTokenInHandWorksUntilItExpires() {
        World w = buildWorld();
        Actor member = w.memberA();
        String refreshToken = refresh.start(member.userId(), member.workspaceId());

        ResponseEntity<JsonNode> suspended = post("/api/v1/members/" + member.userId() + "/suspend", w.owner(), null);
        assertThat(suspended.getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);

        // The API revokes the chain at once, so the refresh is a plain 401 (the chain is already dead), not the
        // 403 MEMBERSHIP_SUSPENDED of the case above. Either way, no new access token.
        Rotation rotation = refresh.rotate(refreshToken);
        assertThat(rotation.accepted()).isFalse();
        assertThat(rotation.status()).isEqualTo(HttpStatus.UNAUTHORIZED);

        // Known design window (TECH-V2-core-api §5.0/§5.6, ADR-007 §5): the token already issued is not re-checked
        // against the membership on every request, so it keeps working until it expires.
        assertThat(get("/api/v1/documents/" + w.docs().get(A).id(), member).getStatusCode())
                .as("window: held access token still reads").isEqualTo(HttpStatus.OK);
        assertThat(lifetimeSeconds(member.token())).isLessThanOrEqualTo(15 * 60);
        // ...but a new token cannot be minted for the suspended member by any path.
        Throwable refused = org.assertj.core.api.Assertions.catchThrowable(
                () -> sessions.reissue(member.userId(), member.workspaceId()));
        assertThat(refused).isInstanceOf(ApiException.class);
        assertThat(((ApiException) refused).code()).isEqualTo("MEMBERSHIP_SUSPENDED");
    }

    @Test
    void archivingDepartmentAKeepsTheDocumentsRestrictedAndTheMembersOfAStillReadThem() {
        World w = buildWorld();
        Doc aOnly = w.docs().get(A);

        ResponseEntity<JsonNode> archived = patch("/api/v1/departments/" + w.deptA(), w.owner(), Map.of("status", "ARCHIVED"));
        assertThat(archived.getStatusCode()).isEqualTo(HttpStatus.OK);

        Actor memberA = actorFor(w.memberA().userId(), w.owner().workspaceId());
        assertThat(verifier.verify(memberA.token()).orElseThrow().departmentId()).isEqualTo(w.deptA());
        assertThat(get("/api/v1/documents/" + aOnly.id(), memberA).getStatusCode()).isEqualTo(HttpStatus.OK);
        for (Actor outsider : List.of(w.memberB(), w.memberNoDept())) {
            ResponseEntity<JsonNode> response = get("/api/v1/documents/" + aOnly.id(), outsider);
            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
            assertNothingLeaksAbout(aOnly, response);
        }
        JsonNode detail = get("/api/v1/documents/" + aOnly.id(), w.owner()).getBody().path("data");
        assertThat(detail.path("visibility").asText()).isEqualTo("DEPARTMENTS");
        assertThat(detail.path("departments")).hasSize(1);
        assertThat(detail.at("/departments/0/id").asText()).isEqualTo(w.deptA().toString());
        assertThat(ai.sentOfType(OutboxEvent.Type.ACCESS_UPDATED)).as("archiving changes no document access").isZero();
    }

    @Test
    void deletingADepartmentThatDocumentsOrMembersStillReferenceIsRefusedWithDepartmentInUse() {
        World w = buildWorld();
        UUID docOnly = createDepartment(w.owner(), "Only docs " + UUID.randomUUID());
        Actor publisherC = addDepartmentPublisher(w.owner().workspaceId(), docOnly, "fr29-pubc");
        Doc scoped = uploadSecret(publisherC, "C", "SECRET_C_4410", "DEPARTMENTS", docOnly);

        ResponseEntity<JsonNode> blockedByDocument = delete("/api/v1/departments/" + docOnly, w.owner());
        assertThat(blockedByDocument.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(blockedByDocument.getBody().at("/error/code").asText()).isEqualTo("DEPARTMENT_IN_USE");
        assertThat(blockedByDocument.getBody().at("/error/details/documents").asInt()).isEqualTo(1);

        ResponseEntity<JsonNode> blockedByMembersAndDocuments = delete("/api/v1/departments/" + w.deptA(), w.owner());
        assertThat(blockedByMembersAndDocuments.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(blockedByMembersAndDocuments.getBody().at("/error/code").asText()).isEqualTo("DEPARTMENT_IN_USE");

        // Nothing was lost: the scope of the document is intact and still enforced.
        assertThat(get("/api/v1/documents/" + scoped.id(), w.owner()).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(get("/api/v1/documents/" + scoped.id(), w.memberNoDept()).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(get("/api/v1/documents/" + w.docs().get(A).id(), w.memberA()).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void anOwnerTransferNarrowingAWorkspaceDocumentToDepartmentAHidesItAtOnceFromOthersAndSendsAccessUpdated()
            throws Exception {
        World w = buildWorld();
        Doc doc = w.docs().get(WS);
        for (Actor reader : List.of(w.memberA(), w.memberB(), w.memberNoDept())) {
            assertThat(get("/api/v1/documents/" + doc.id(), reader).getStatusCode()).isEqualTo(HttpStatus.OK);
        }
        dispatcher.dispatchDue();
        ai.reset();

        // Switching the kind of a document hands it to a department: the OWNER's PUT /ownership (ADR-009).
        ResponseEntity<JsonNode> narrowed = put("/api/v1/documents/" + doc.id() + "/ownership", w.owner(),
                Map.of("visibility", "DEPARTMENTS", "ownerDepartmentId", w.deptA().toString(),
                        "departmentIds", List.of(w.deptA().toString())));

        assertThat(narrowed.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(get("/api/v1/documents/" + doc.id(), w.memberA()).getStatusCode()).isEqualTo(HttpStatus.OK);
        for (Actor outsider : List.of(w.memberB(), w.memberNoDept())) {
            for (String path : List.of("/api/v1/documents/" + doc.id(),
                    "/api/v1/documents/" + doc.id() + "/download-url")) {
                ResponseEntity<JsonNode> response = get(path, outsider);
                assertThat(response.getStatusCode()).as(path).isEqualTo(HttpStatus.NOT_FOUND);
                assertNothingLeaksAbout(doc, response);
            }
            assertNothingLeaksAbout(doc, get("/api/v1/documents?limit=100", outsider));
            assertThat(get("/api/v1/documents?limit=100&q=" + doc.title(), outsider)
                    .getBody().path("data")).isEmpty();
        }
        List<OutboxEvent> access = ai.sent().stream().filter(e -> e.type() == OutboxEvent.Type.ACCESS_UPDATED).toList();
        assertThat(access).hasSize(1);
        JsonNode payload = json.readTree(access.get(0).payload());
        assertThat(access.get(0).aggregateId()).isEqualTo(doc.id());
        assertThat(payload.path("visibility").asText()).isEqualTo("DEPARTMENTS");
        assertThat(payload.at("/departmentIds/0").asText()).isEqualTo(w.deptA().toString());
        assertThat(payload.path("departmentIds")).hasSize(1);
        assertThat(payload.path("accessRevision").asLong()).as("revision 1 at upload, 2 after the change").isEqualTo(2);
        assertThat(payload.path("workspaceId").asText()).isEqualTo(w.owner().workspaceId().toString());
    }

    // ---- helpers ------------------------------------------------------------------------------------

    private static List<String> idsOf(ResponseEntity<JsonNode> response) {
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return java.util.stream.StreamSupport.stream(response.getBody().path("data").spliterator(), false)
                .map(n -> n.path("id").asText()).toList();
    }

    /** {@code exp - iat} of an access token, read from its payload (the signature was checked when it was issued). */
    private long lifetimeSeconds(String token) {
        try {
            JsonNode claims = json.readTree(Base64.getUrlDecoder().decode(token.split("\\.")[1]));
            return claims.path("exp").asLong() - claims.path("iat").asLong();
        } catch (java.io.IOException e) {
            throw new IllegalStateException("Token payload is unreadable", e);
        }
    }
}
