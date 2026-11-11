package com.sopilot.core.document;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.outbox.OutboxEvent;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * V2-36 / ADR-009: who may write a document. Publishers of a department write that department's documents,
 * the workspace publisher writes {@code WORKSPACE} documents, an OWNER recalls (deletes) and transfers but never
 * writes content, ADMIN has no write access. Read isolation (FR-29) is covered again next to the new data.
 */
class DocumentPublisherIT extends ApiIT {

    // ---- fixtures -------------------------------------------------------------------------------

    private UUID department(Actor owner, String name) {
        ResponseEntity<JsonNode> created = post("/api/v1/departments", owner, Map.of("name", name));
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return id(created, "id");
    }

    private ResponseEntity<JsonNode> report(UUID workspaceId, UUID doc, UUID ver, String status) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", "test-internal-token");
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("workspaceId", workspaceId.toString());
        body.put("status", status);
        body.put("attempt", 0);
        if ("READY".equals(status)) {
            body.put("pageCount", 3);
            body.put("detectedLanguage", "vi");
            body.put("chunkCount", 12);
            body.put("embedding", Map.of("provider", "local", "model", "BAAI/bge-m3", "revision", "abc", "dim", 1024));
            body.put("extracted", Map.of());
            body.put("warningCodes", List.of());
        }
        if ("FAILED".equals(status)) {
            body.put("failureCode", "EXTRACTION_FAILED");
            body.put("failureMessage", "boom");
        }
        return http.exchange("/internal/documents/" + doc + "/versions/" + ver + "/status", HttpMethod.PATCH,
                new HttpEntity<>(body, headers), JsonNode.class);
    }

    /** Walks the latest version to READY, as ai-service would. */
    private void ready(Actor viewer, UUID doc) {
        UUID ver = id(get("/api/v1/documents/" + doc, viewer), "latestVersion", "id");
        report(viewer.workspaceId(), doc, ver, "PROCESSING");
        assertThat(report(viewer.workspaceId(), doc, ver, "READY").getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    private UUID uploaded(ResponseEntity<JsonNode> response) {
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return id(response, "id");
    }

    private static void assertCode(ResponseEntity<JsonNode> response, HttpStatus status, String code) {
        assertThat(response.getStatusCode()).isEqualTo(status);
        assertThat(response.getBody().at("/error/code").asText()).isEqualTo(code);
    }

    private ResponseEntity<JsonNode> setVisibility(Actor actor, UUID doc, String visibility, UUID... departments) {
        return put("/api/v1/documents/" + doc + "/visibility", actor, Map.of("visibility", visibility,
                "departmentIds", java.util.Arrays.stream(departments).map(UUID::toString).toList()));
    }

    private ResponseEntity<JsonNode> transfer(Actor actor, UUID doc, String visibility, UUID ownerDepartment,
                                              UUID... departments) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("visibility", visibility);
        body.put("ownerDepartmentId", ownerDepartment == null ? null : ownerDepartment.toString());
        body.put("departmentIds", java.util.Arrays.stream(departments).map(UUID::toString).toList());
        return put("/api/v1/documents/" + doc + "/ownership", actor, body);
    }

    private String ownerOf(Actor viewer, UUID doc) {
        return asTenant(viewer, () -> jdbc.queryForObject("SELECT coalesce(owner_department_id::text, '-') "
                + "FROM core.documents WHERE id = ?", String.class, doc));
    }

    // ---- the right publisher --------------------------------------------------------------------

    @Test
    void aDepartmentPublisherDoesEverythingOnTheirDepartmentsDocuments() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor publisher = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");

        UUID doc = uploaded(uploadToDepartments(publisher, "a.md", markdown("a"), d));
        assertThat(ownerOf(owner, doc)).isEqualTo(d.toString());
        ready(owner, doc);

        // Replace: a new version; the old READY version keeps answering until the new one is READY.
        ResponseEntity<JsonNode> second = upload("/api/v1/documents/" + doc + "/versions", publisher, "a2.md",
                markdown("a2"));
        assertThat(second.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        UUID v2 = id(second, "latestVersion", "id");
        report(owner.workspaceId(), doc, v2, "PROCESSING");
        report(owner.workspaceId(), doc, v2, "FAILED");
        assertThat(post("/api/v1/documents/" + doc + "/retry", publisher, null).getStatusCode()).isEqualTo(HttpStatus.OK);

        assertThat(patch("/api/v1/documents/" + doc, publisher, Map.of("title", "Báo cáo")).getStatusCode())
                .isEqualTo(HttpStatus.OK);
        // Same kind of document, owner department kept: widening the readers is the publisher's call.
        assertThat(setVisibility(publisher, doc, "DEPARTMENTS", d, d2).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(get("/api/v1/documents/" + doc + "/versions", publisher).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(delete("/api/v1/documents/" + doc, publisher).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);

        JsonNode audit = get("/api/v1/audit-logs?action=DOCUMENT_DELETED", owner).getBody().path("data");
        assertThat(audit.get(0).at("/details/actingAs").asText()).isEqualTo("DEPARTMENT_PUBLISHER");
        assertThat(audit.get(0).at("/details/ownerDepartmentId").asText()).isEqualTo(d.toString());
        assertThat(get("/api/v1/audit-logs?action=DOCUMENT_UPLOADED", owner).getBody().path("data").get(0)
                .at("/details/ownerDepartmentId").asText()).isEqualTo(d.toString());
    }

    @Test
    void theWorkspacePublisherDoesEverythingOnWorkspaceDocuments() {
        Actor owner = newTeamWorkspace("own");
        Actor publisher = addMember(owner.workspaceId(), "MEMBER", "wsp");
        seedWorkspacePublisher(owner.workspaceId(), publisher.userId());

        UUID doc = uploaded(uploadDocument(publisher, "a.md", markdown("a")));
        ready(owner, doc);
        assertThat(ownerOf(owner, doc)).isEqualTo("-");
        assertThat(upload("/api/v1/documents/" + doc + "/versions", publisher, "a2.md", markdown("a2")).getStatusCode())
                .isEqualTo(HttpStatus.CREATED);
        assertThat(patch("/api/v1/documents/" + doc, publisher, Map.of("title", "T")).getStatusCode())
                .isEqualTo(HttpStatus.OK);
        assertThat(setVisibility(publisher, doc, "WORKSPACE").getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(delete("/api/v1/documents/" + doc, publisher).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(get("/api/v1/audit-logs?action=DOCUMENT_DELETED", owner).getBody().path("data").get(0)
                .at("/details/actingAs").asText()).isEqualTo("WORKSPACE_PUBLISHER");
    }

    // ---- the wrong publisher --------------------------------------------------------------------

    @Test
    void anotherDepartmentsPublisherIsRefusedOnAReadableDocumentAndNotFoundOnAHiddenOne() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor pubD = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        Actor pubD2 = addDepartmentPublisher(owner.workspaceId(), d2, "pub-d2");
        UUID shared = uploaded(uploadToDepartments(pubD, "shared.md", markdown("s"), d, d2));
        UUID hidden = uploaded(uploadToDepartments(pubD, "hidden.md", markdown("h"), d));
        UUID wide = uploaded(uploadDocument(owner, "wide.md", markdown("w")));

        // D2 can read the shared document (it is listed) but D owns it: 403 on every write.
        String path = "/api/v1/documents/" + shared;
        for (ResponseEntity<JsonNode> r : List.of(
                upload(path + "/versions", pubD2, "x.md", markdown("x")),
                post(path + "/retry", pubD2, null),
                patch(path, pubD2, Map.of("title", "x")),
                setVisibility(pubD2, shared, "DEPARTMENTS", d, d2),
                delete(path, pubD2))) {
            assertCode(r, HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        }
        // D2 cannot read the hidden one: the same writes are 404 and name nothing.
        String hiddenPath = "/api/v1/documents/" + hidden;
        for (ResponseEntity<JsonNode> r : List.of(
                upload(hiddenPath + "/versions", pubD2, "x.md", markdown("x")),
                post(hiddenPath + "/retry", pubD2, null),
                patch(hiddenPath, pubD2, Map.of("title", "x")),
                delete(hiddenPath, pubD2))) {
            assertThat(r.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
            assertThat(r.getBody().toString()).doesNotContain("hidden").doesNotContain(hidden.toString());
        }
        // A department publisher does not publish workspace documents, nor create them.
        assertCode(patch("/api/v1/documents/" + wide, pubD, Map.of("title", "x")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertCode(uploadDocument(pubD, "ws.md", markdown("ws")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        // Creating for a department you do not publish for.
        assertCode(uploadOwnedBy(pubD2, "o.md", markdown("o"), d, d2, d), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(uploadToDepartments(pubD2, "ok.md", markdown("ok"), d2, d).getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }

    @Test
    void adminWhoIsNotAPublisherIsRefusedOnEveryWriteButStillManagesAndReadsEverything() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");
        Actor pubD = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        UUID dept = uploaded(uploadToDepartments(pubD, "d.md", markdown("d"), d));
        UUID wide = uploaded(uploadDocument(owner, "w.md", markdown("w")));

        for (UUID doc : List.of(dept, wide)) {
            String path = "/api/v1/documents/" + doc;
            for (ResponseEntity<JsonNode> r : List.of(
                    upload(path + "/versions", admin, "x.md", markdown("x")),
                    post(path + "/retry", admin, null),
                    patch(path, admin, Map.of("title", "x")),
                    setVisibility(admin, doc, doc.equals(wide) ? "WORKSPACE" : "DEPARTMENTS", d),
                    delete(path, admin))) {
                assertCode(r, HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
            }
        }
        assertCode(uploadDocument(admin, "n.md", markdown("n")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertCode(uploadToDepartments(admin, "n2.md", markdown("n2"), d), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");

        // Still the manager of everything else, and reads every document.
        assertThat(post("/api/v1/departments", admin, Map.of("name", "Kho")).getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(post("/api/v1/categories", admin, Map.of("name", "Chính sách")).getStatusCode())
                .isEqualTo(HttpStatus.CREATED);
        assertThat(get("/api/v1/documents", admin).getBody().path("data")).hasSize(2);
        assertThat(get("/api/v1/documents/" + dept + "/versions", admin).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertCode(put("/api/v1/departments/" + d + "/publisher", admin, Map.of("userId", pubD.userId().toString())),
                HttpStatus.FORBIDDEN, "FORBIDDEN");
    }

    @Test
    void anOwnerWhoIsNotAPublisherCannotWriteButCanRecallAnyDocumentEvenOfAnUnstaffedDepartment() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor pubD = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        UUID dept = uploaded(uploadToDepartments(pubD, "d.md", markdown("d"), d));
        Actor second = addMember(owner.workspaceId(), "OWNER", "own2");   // an OWNER who publishes nothing

        String path = "/api/v1/documents/" + dept;
        for (ResponseEntity<JsonNode> r : List.of(
                upload(path + "/versions", second, "x.md", markdown("x")),
                post(path + "/retry", second, null),
                patch(path, second, Map.of("title", "x")),
                setVisibility(second, dept, "DEPARTMENTS", d))) {
            assertCode(r, HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        }
        assertCode(uploadToDepartments(second, "n.md", markdown("n"), d), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");

        // The department loses its publisher; the OWNER can still delete.
        assertThat(delete("/api/v1/departments/" + d + "/publisher", owner).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(delete(path, second).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        JsonNode audit = get("/api/v1/audit-logs?action=DOCUMENT_DELETED", owner).getBody().path("data");
        assertThat(audit.get(0).at("/details/actingAs").asText()).isEqualTo("OWNER");
    }

    @Test
    void anOwnerDemotedSinceSigningInCannotRecallAnymore() {
        Actor owner = newTeamWorkspace("own");
        Actor second = addMember(owner.workspaceId(), "OWNER", "own2");
        UUID doc = uploaded(uploadDocument(owner, "a.md", markdown("a")));
        assertThat(patch("/api/v1/members/" + second.userId(), owner, Map.of("role", "ADMIN")).getStatusCode())
                .isEqualTo(HttpStatus.OK);

        // `second` still holds a token whose role is OWNER.
        assertCode(delete("/api/v1/documents/" + doc, second), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(get("/api/v1/documents/" + doc, owner).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    // ---- assigning publishers -------------------------------------------------------------------

    @Test
    void onlyAnOwnerAssignsAndTheOldPublisherLosesAccessAtTheNextRequestWithoutRefresh() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor a = addDepartmentPublisher(owner.workspaceId(), d, "pub-a");
        Actor b = addMember(owner.workspaceId(), "MEMBER", "pub-b");
        assertThat(patch("/api/v1/members/" + b.userId(), owner, Map.of("departmentId", d.toString())).getStatusCode())
                .isEqualTo(HttpStatus.OK);
        b = actorFor(b.userId(), owner.workspaceId());
        UUID doc = uploaded(uploadToDepartments(a, "a.md", markdown("a"), d));
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");

        String assign = "/api/v1/departments/" + d + "/publisher";
        assertCode(put(assign, admin, Map.of("userId", b.userId().toString())), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertCode(put(assign, a, Map.of("userId", b.userId().toString())), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertCode(delete(assign, admin), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertThat(patch("/api/v1/documents/" + doc, b, Map.of("title", "b")).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);

        assertThat(put(assign, owner, Map.of("userId", b.userId().toString())).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);

        // Same tokens as before: the database decides.
        assertCode(patch("/api/v1/documents/" + doc, a, Map.of("title", "a again")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(patch("/api/v1/documents/" + doc, b, Map.of("title", "by b")).getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode audit = get("/api/v1/audit-logs?action=PUBLISHER_ASSIGNED", owner).getBody().path("data");
        assertThat(audit.get(0).at("/details/reason").asText()).isEqualTo("OWNER_ACTION");
        assertThat(audit.get(0).at("/details/previousUserId").asText()).isEqualTo(a.userId().toString());
    }

    @Test
    void assigningChecksDepartmentMembershipStatusAndArchival() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID other = department(owner, "Legal");
        Actor inOther = addMember(owner.workspaceId(), "MEMBER", "legal");
        patch("/api/v1/members/" + inOther.userId(), owner, Map.of("departmentId", other.toString()));
        Actor inD = addMember(owner.workspaceId(), "MEMBER", "fin");
        patch("/api/v1/members/" + inD.userId(), owner, Map.of("departmentId", d.toString()));
        Actor stranger = newTeamWorkspace("stranger");
        String assign = "/api/v1/departments/" + d + "/publisher";

        assertCode(put(assign, owner, Map.of("userId", inOther.userId().toString())), HttpStatus.CONFLICT,
                "PUBLISHER_NOT_IN_DEPARTMENT");
        assertCode(put(assign, owner, Map.of("userId", stranger.userId().toString())), HttpStatus.CONFLICT,
                "MEMBER_NOT_ACTIVE");
        assertThat(post("/api/v1/members/" + inD.userId() + "/suspend", owner, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertCode(put(assign, owner, Map.of("userId", inD.userId().toString())), HttpStatus.CONFLICT, "MEMBER_NOT_ACTIVE");
        assertThat(post("/api/v1/members/" + inD.userId() + "/reactivate", owner, null).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(put(assign, owner, Map.of("userId", inD.userId().toString())).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        patch("/api/v1/departments/" + other, owner, Map.of("status", "ARCHIVED"));
        assertCode(put("/api/v1/departments/" + other + "/publisher", owner, Map.of("userId", inOther.userId().toString())),
                HttpStatus.CONFLICT, "DEPARTMENT_ARCHIVED");
        // A department of another workspace is not found; removing a missing publisher is idempotent.
        assertThat(put("/api/v1/departments/" + d + "/publisher", stranger, Map.of("userId", inD.userId().toString()))
                .getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(delete("/api/v1/departments/" + other + "/publisher", owner).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(delete("/api/v1/departments/" + other + "/publisher", owner).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
    }

    @Test
    void theWorkspacePublisherIsAssignedByAnOwnerAndTheListShowsNoEmail() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor pub = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");

        assertCode(put("/api/v1/publishers/workspace", member, Map.of("userId", pub.userId().toString())),
                HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertThat(put("/api/v1/publishers/workspace", owner, Map.of("userId", pub.userId().toString())).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);

        ResponseEntity<JsonNode> list = get("/api/v1/publishers", member);
        assertThat(list.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(list.getBody().at("/data/workspace/userId").asText()).isEqualTo(pub.userId().toString());
        assertThat(list.getBody().at("/data/departments/0/departmentId").asText()).isEqualTo(d.toString());
        assertThat(list.getBody().at("/data/departments/0/publisher/userId").asText()).isEqualTo(pub.userId().toString());
        assertThat(list.getBody().toString()).doesNotContain("@");

        // The owner who created the workspace no longer publishes workspace documents.
        assertCode(uploadDocument(owner, "x.md", markdown("x")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(delete("/api/v1/publishers/workspace", owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertCode(uploadDocument(pub, "y.md", markdown("y")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(get("/api/v1/publishers", member).getBody().at("/data/workspace").isNull()).isTrue();
    }

    @Test
    void theCreatorOfAWorkspaceAndOfAPersonalWorkspaceIsItsWorkspacePublisher() {
        Actor me = loginPersonal("creator");

        assertThat(get("/api/v1/publishers", me).getBody().at("/data/workspace/userId").asText())
                .isEqualTo(me.userId().toString());
        assertThat(uploadDocument(me, "mine.md", markdown("mine")).getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(get("/api/v1/members/me", me).getBody().at("/data/publisherOf/workspace").asBoolean()).isTrue();

        ResponseEntity<JsonNode> team = post("/api/v1/workspaces", me, Map.of("name", "Acme"));
        assertThat(team.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        Actor inTeam = new Actor(me.userId(), id(team, "workspace", "id"), com.sopilot.core.security.WorkspaceRole.OWNER,
                team.getBody().at("/data/accessToken").asText());
        assertThat(get("/api/v1/publishers", inTeam).getBody().at("/data/workspace/userId").asText())
                .isEqualTo(me.userId().toString());
        assertThat(uploadDocument(inTeam, "team.md", markdown("team")).getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }

    // ---- publisher stays tied to the department ------------------------------------------------

    @Test
    void movingAPublisherToAnotherDepartmentRemovesTheRoleInTheSameTransaction() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor pub = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        UUID doc = uploaded(uploadToDepartments(pub, "a.md", markdown("a"), d, d2));

        assertThat(patch("/api/v1/members/" + pub.userId(), owner, Map.of("departmentId", d2.toString())).getStatusCode())
                .isEqualTo(HttpStatus.OK);

        assertCode(patch("/api/v1/documents/" + doc, pub, Map.of("title", "x")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(get("/api/v1/publishers", owner).getBody().at("/data/departments/0/publisher").isNull()
                && get("/api/v1/publishers", owner).getBody().at("/data/departments/1/publisher").isNull()).isTrue();
        JsonNode audit = get("/api/v1/audit-logs?action=PUBLISHER_UNASSIGNED", owner).getBody().path("data");
        assertThat(audit).hasSize(1);
        assertThat(audit.get(0).at("/details/reason").asText()).isEqualTo("DEPARTMENT_CHANGED");
        // With nobody publishing for D, nothing owned by D can be created or changed except by recall.
        Actor other = addMember(owner.workspaceId(), "MEMBER", "other");
        patch("/api/v1/members/" + other.userId(), owner, Map.of("departmentId", d.toString()));
        assertCode(uploadToDepartments(actorFor(other.userId(), owner.workspaceId()), "n.md", markdown("n"), d),
                HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
    }

    @Test
    void removingOrLeavingTheWorkspaceEndsPublishingWithAnAuditEntry() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor pub = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        Actor ws = addMember(owner.workspaceId(), "MEMBER", "wsp");
        seedWorkspacePublisher(owner.workspaceId(), ws.userId());

        assertThat(delete("/api/v1/members/" + pub.userId(), owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(post("/api/v1/members/leave", ws, null).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);

        Long rows = asTenant(owner, () -> jdbc.queryForObject("SELECT (SELECT count(*) FROM core.department_publishers) "
                + "+ (SELECT count(*) FROM core.workspace_publishers WHERE user_id <> ?)", Long.class, owner.userId()));
        assertThat(rows).isZero();
        JsonNode audit = get("/api/v1/audit-logs?action=PUBLISHER_UNASSIGNED", owner).getBody().path("data");
        assertThat(audit).hasSize(2);
        assertThat(audit.get(0).at("/details/reason").asText()).isEqualTo("MEMBER_REMOVED");
    }

    // ---- READY versions stay put ---------------------------------------------------------------

    @Test
    void changingOrRemovingThePublisherDoesNotTouchTheReadyVersion() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor a = addDepartmentPublisher(owner.workspaceId(), d, "pub-a");
        UUID doc = uploaded(uploadToDepartments(a, "a.md", markdown("a"), d));
        ready(owner, doc);
        String before = asTenant(owner, () -> jdbc.queryForObject("SELECT current_version_id::text || status "
                + "FROM core.documents d JOIN core.document_versions v ON v.id = d.current_version_id WHERE d.id = ?",
                String.class, doc));
        long eventsBefore = asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events "
                + "WHERE aggregate_id = ?", Long.class, doc));

        assertThat(delete("/api/v1/departments/" + d + "/publisher", owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);

        String after = asTenant(owner, () -> jdbc.queryForObject("SELECT current_version_id::text || status "
                + "FROM core.documents d JOIN core.document_versions v ON v.id = d.current_version_id WHERE d.id = ?",
                String.class, doc));
        assertThat(after).isEqualTo(before).endsWith("READY");
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events "
                + "WHERE aggregate_id = ?", Long.class, doc))).isEqualTo(eventsBefore);
        assertThat(data(get("/api/v1/documents/" + doc, owner)).path("answerable").asBoolean()).isTrue();
    }

    private static JsonNode data(ResponseEntity<JsonNode> r) {
        return r.getBody().path("data");
    }

    // ---- publisher cannot change who is responsible ---------------------------------------------

    @Test
    void aPublisherCannotSwitchTheKindOrDropTheOwnerDepartmentAndTheDatabaseAgrees() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor pub = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        UUID doc = uploaded(uploadToDepartments(pub, "a.md", markdown("a"), d, d2));

        assertCode(setVisibility(pub, doc, "WORKSPACE"), HttpStatus.CONFLICT, "OWNERSHIP_CHANGE_REQUIRES_OWNER");
        assertCode(setVisibility(pub, doc, "DEPARTMENTS", d2), HttpStatus.CONFLICT, "OWNERSHIP_CHANGE_REQUIRES_OWNER");
        assertCode(transfer(pub, doc, "WORKSPACE", null), HttpStatus.FORBIDDEN, "FORBIDDEN");

        // The deferred foreign key stops a raw attempt to drop the owner department from the reader list.
        assertThatThrownBy(() -> asTenant(owner, () -> jdbc.update("DELETE FROM core.document_departments "
                + "WHERE document_id = ? AND department_id = ?", doc, d)))
                .rootCause().hasMessageContaining("fk_documents_owner_in_scope");
    }

    @Test
    void whenTheOwnerDepartmentIsArchivedThePublisherIsToldWhyAndTheOwnerCanTransfer() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Purchasing");
        UUID other = department(owner, "Procurement");
        Actor pub = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        UUID doc = uploaded(uploadToDepartments(pub, "a.md", markdown("a"), d));
        patch("/api/v1/departments/" + d, owner, Map.of("status", "ARCHIVED"));

        // Whatever the publisher asks, the answer names the real cause.
        assertCode(setVisibility(pub, doc, "DEPARTMENTS", d), HttpStatus.CONFLICT, "OWNER_DEPARTMENT_ARCHIVED");
        assertCode(setVisibility(pub, doc, "DEPARTMENTS", d, other), HttpStatus.CONFLICT, "OWNER_DEPARTMENT_ARCHIVED");
        assertCode(setVisibility(pub, doc, "DEPARTMENTS", other), HttpStatus.CONFLICT, "OWNER_DEPARTMENT_ARCHIVED");
        // The rest of the publisher's rights are unchanged, and the readers did not move.
        assertThat(patch("/api/v1/documents/" + doc, pub, Map.of("title", "Still editable")).getStatusCode())
                .isEqualTo(HttpStatus.OK);
        assertThat(data(get("/api/v1/documents/" + doc, owner)).path("departments")).hasSize(1);

        // Not the publisher's to change, but another publisher or an outsider still learns nothing about it.
        Actor outsider = addMember(owner.workspaceId(), "MEMBER", "out");
        assertThat(setVisibility(outsider, doc, "DEPARTMENTS", d).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);

        // The way out the message names: the OWNER transfers the document to an active department.
        assertThat(transfer(owner, doc, "DEPARTMENTS", other, other).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(ownerOf(owner, doc)).isEqualTo(other.toString());
    }

    // ---- transfer of responsibility -------------------------------------------------------------

    @Test
    void anOwnerTransfersResponsibilityInAllThreeWaysWithoutTouchingVersionsAndOnlyAnOwnerCan() throws Exception {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor pubD = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        Actor pubD2 = addDepartmentPublisher(owner.workspaceId(), d2, "pub-d2");
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");
        UUID doc = uploaded(uploadToDepartments(pubD, "a.md", markdown("a"), d));
        ready(owner, doc);
        String versionBefore = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT current_version_id::text FROM core.documents WHERE id = ?", String.class, doc));
        dispatcher.dispatchDue();
        ai.reset();

        // Nobody else may transfer.
        assertCode(transfer(admin, doc, "WORKSPACE", null), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertCode(transfer(pubD, doc, "WORKSPACE", null), HttpStatus.FORBIDDEN, "FORBIDDEN");

        // DEPARTMENTS -> DEPARTMENTS: another owner department.
        ResponseEntity<JsonNode> moved = transfer(owner, doc, "DEPARTMENTS", d2, d2);
        assertThat(moved.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(moved.getBody().at("/data/publisherAssigned").asBoolean()).isTrue();
        assertThat(ownerOf(owner, doc)).isEqualTo(d2.toString());
        assertCode(patch("/api/v1/documents/" + doc, pubD, Map.of("title", "old")), HttpStatus.NOT_FOUND, "NOT_FOUND");
        assertThat(patch("/api/v1/documents/" + doc, pubD2, Map.of("title", "new")).getStatusCode()).isEqualTo(HttpStatus.OK);

        // DEPARTMENTS -> WORKSPACE: the workspace publisher (the owner) takes over.
        assertThat(transfer(owner, doc, "WORKSPACE", null).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(ownerOf(owner, doc)).isEqualTo("-");
        assertCode(patch("/api/v1/documents/" + doc, pubD2, Map.of("title", "x")), HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(patch("/api/v1/documents/" + doc, owner, Map.of("title", "ws")).getStatusCode()).isEqualTo(HttpStatus.OK);

        // WORKSPACE -> DEPARTMENTS: back to Finance, which has a publisher.
        assertThat(transfer(owner, doc, "DEPARTMENTS", d, d, d2).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(patch("/api/v1/documents/" + doc, pubD, Map.of("title", "fin")).getStatusCode()).isEqualTo(HttpStatus.OK);

        // Versions, status and the Q&A version are unchanged; every transfer sent ACCESS_UPDATED with a new revision.
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT current_version_id::text FROM core.documents "
                + "WHERE id = ?", String.class, doc))).isEqualTo(versionBefore);
        assertThat(data(get("/api/v1/documents/" + doc, owner)).path("answerable").asBoolean()).isTrue();
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.document_versions "
                + "WHERE document_id = ?", Long.class, doc))).isEqualTo(1L);
        assertThat(ai.sentOfType(OutboxEvent.Type.ACCESS_UPDATED)).isEqualTo(3);
        String payload = asTenant(owner, () -> jdbc.queryForObject("SELECT payload::text FROM core.outbox_events "
                + "WHERE aggregate_id = ? AND event_type = 'ACCESS_UPDATED' ORDER BY created_at DESC LIMIT 1",
                String.class, doc));
        assertThat(json.readTree(payload).at("/accessRevision").asInt()).isEqualTo(4);
        assertThat(payload).doesNotContain("owner");
        JsonNode audit = get("/api/v1/audit-logs?action=DOCUMENT_OWNERSHIP_CHANGED", owner).getBody().path("data");
        assertThat(audit).hasSize(3);
        assertThat(audit.get(2).at("/details/from/ownerDepartmentId").asText()).isEqualTo(d.toString());
        assertThat(audit.get(2).at("/details/to/ownerDepartmentId").asText()).isEqualTo(d2.toString());
    }

    @Test
    void aTransferIsValidatedAndTellsTheOwnerWhenNobodyPublishesTheNewScope() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID unstaffed = department(owner, "Kho");
        UUID archived = department(owner, "Cũ");
        Actor pub = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        UUID doc = uploaded(uploadToDepartments(pub, "a.md", markdown("a"), d));
        patch("/api/v1/departments/" + archived, owner, Map.of("status", "ARCHIVED"));

        assertCode(transfer(owner, doc, "DEPARTMENTS", archived, archived), HttpStatus.CONFLICT, "DEPARTMENT_ARCHIVED");
        assertCode(transfer(owner, doc, "DEPARTMENTS", d, unstaffed), HttpStatus.BAD_REQUEST,
                "OWNER_DEPARTMENT_NOT_IN_SCOPE");
        assertCode(transfer(owner, doc, "DEPARTMENTS", null, d), HttpStatus.BAD_REQUEST, "OWNER_DEPARTMENT_NOT_IN_SCOPE");
        assertThat(transfer(owner, doc, "WORKSPACE", d).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(transfer(owner, UUID.randomUUID(), "WORKSPACE", null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);

        ResponseEntity<JsonNode> toUnstaffed = transfer(owner, doc, "DEPARTMENTS", unstaffed, unstaffed);
        assertThat(toUnstaffed.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(toUnstaffed.getBody().at("/data/publisherAssigned").asBoolean()).isFalse();
        assertCode(patch("/api/v1/documents/" + doc, pub, Map.of("title", "x")), HttpStatus.NOT_FOUND, "NOT_FOUND");
    }

    // ---- reads ----------------------------------------------------------------------------------

    @Test
    void publishersSeeAdministrativeFieldsOnlyOnTheirOwnDocumentsAndReadNothingExtra() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor pubD = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        Actor pubD2 = addDepartmentPublisher(owner.workspaceId(), d2, "pub-d2");
        Actor outsider = addMember(owner.workspaceId(), "MEMBER", "out");
        UUID mine = uploaded(uploadToDepartments(pubD, "mine.md", markdown("mine"), d));
        UUID theirs = uploaded(uploadToDepartments(pubD2, "theirs.md", markdown("theirs"), d2));
        UUID shared = uploaded(uploadToDepartments(pubD, "shared.md", markdown("shared"), d, d2));

        JsonNode asPublisher = data(get("/api/v1/documents/" + mine, pubD));
        assertThat(asPublisher.path("departments")).hasSize(1);
        assertThat(asPublisher.path("fieldSources").isMissingNode() || asPublisher.path("fieldSources").isNull()).isFalse();
        assertThat(asPublisher.at("/ownerDepartment/id").asText()).isEqualTo(d.toString());
        // D2 reads `shared` but is not its publisher: masked like any member.
        JsonNode asOther = data(get("/api/v1/documents/" + shared, pubD2));
        assertThat(asOther.path("departments").isNull()).isTrue();
        assertThat(asOther.path("fieldSources").isNull()).isTrue();
        assertThat(get("/api/v1/documents/" + shared + "/versions", pubD2).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);

        // Matrix of reads is the one of ADR-007 section 4.4: a publisher reads no more than their department.
        assertThat(get("/api/v1/documents/" + theirs, pubD).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(get("/api/v1/documents/" + theirs + "/download-url", pubD).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(get("/api/v1/documents", pubD).getBody().path("data")).hasSize(2);
        for (UUID doc : List.of(mine, theirs, shared)) {
            assertThat(get("/api/v1/documents/" + doc, outsider).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        }
        assertThat(get("/api/v1/documents", outsider).getBody().path("data")).isEmpty();
        assertThat(get("/api/v1/documents", owner).getBody().path("data")).hasSize(3);

        // The version history says who uploaded each version and when.
        JsonNode versions = get("/api/v1/documents/" + mine + "/versions", pubD).getBody().path("data");
        assertThat(versions.get(0).at("/uploadedBy/id").asText()).isEqualTo(pubD.userId().toString());
        assertThat(versions.get(0).path("uploadedAt").asText()).isNotBlank();
        assertThat(get("/api/v1/members/me", pubD).getBody().at("/data/publisherOf/departmentId").asText())
                .isEqualTo(d.toString());
        assertThat(get("/api/v1/members/me", outsider).getBody().at("/data/publisherOf/workspace").asBoolean()).isFalse();
    }

    @Test
    void theIngestAndAccessPayloadsStayFreeOfTheOwnerDepartment() {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor pub = addDepartmentPublisher(owner.workspaceId(), d, "pub-d");
        UUID doc = uploaded(uploadToDepartments(pub, "a.md", markdown("a"), d));
        setVisibility(pub, doc, "DEPARTMENTS", d);

        List<String> payloads = asTenant(owner, () -> jdbc.queryForList("SELECT payload::text FROM core.outbox_events "
                + "WHERE aggregate_id = ?", String.class, doc));
        assertThat(payloads).hasSize(2).noneMatch(p -> p.contains("owner"));
    }

    // ---- races ----------------------------------------------------------------------------------

    @Test
    void aWriteInFlightHoldsBackAReassignmentAndTheOldPublisherIsRefusedOnceItCommits() throws Exception {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor a = addDepartmentPublisher(owner.workspaceId(), d, "pub-a");
        Actor b = addDepartmentPublisher(owner.workspaceId(), d, "pub-b");
        // addDepartmentPublisher for b replaced a; put a back so there is something to take away.
        seedDepartmentPublisher(owner.workspaceId(), d, a.userId());
        UUID doc = uploaded(uploadToDepartments(a, "a.md", markdown("a"), d));

        // The reassignment holds the publisher row; A's next upload waits for it, then reads the new publisher.
        CompletableFuture<ResponseEntity<JsonNode>> oldPublisherWrite = new CompletableFuture<>();
        asTenant(owner, () -> {
            jdbc.queryForList("SELECT user_id FROM core.department_publishers WHERE department_id = ? FOR UPDATE",
                    UUID.class, d);
            CompletableFuture.runAsync(() -> oldPublisherWrite.complete(
                    uploadToDepartments(a, "late.md", markdown("late"), d)));
            try {
                Thread.sleep(800);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            assertThat(oldPublisherWrite).as("the write waits for the reassignment").isNotDone();
            jdbc.update("UPDATE core.department_publishers SET user_id = ? WHERE department_id = ?", b.userId(), d);
            return null;
        });

        ResponseEntity<JsonNode> late = oldPublisherWrite.get(10, TimeUnit.SECONDS);
        assertCode(late, HttpStatus.FORBIDDEN, "NOT_PUBLISHER");
        assertThat(patch("/api/v1/documents/" + doc, b, Map.of("title", "b")).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void assigningAPublisherWhileTheirDepartmentIsBeingChangedNeverLeavesAStaleRow() throws Exception {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mover");
        patch("/api/v1/members/" + member.userId(), owner, Map.of("departmentId", d.toString()));

        // The department change has updated the membership row but not committed yet: the assignment must wait
        // for it, then see the new department and refuse.
        CompletableFuture<ResponseEntity<JsonNode>> assignment = new CompletableFuture<>();
        asTenant(owner, () -> {
            jdbc.update("UPDATE core.memberships SET department_id = ? WHERE workspace_id = ? AND user_id = ?",
                    d2, owner.workspaceId(), member.userId());
            CompletableFuture.runAsync(() -> assignment.complete(
                    put("/api/v1/departments/" + d + "/publisher", owner, Map.of("userId", member.userId().toString()))));
            try {
                Thread.sleep(800);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            assertThat(assignment).as("the assignment waits for the department change").isNotDone();
            return null;
        });

        assertCode(assignment.get(10, TimeUnit.SECONDS), HttpStatus.CONFLICT, "PUBLISHER_NOT_IN_DEPARTMENT");
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.department_publishers",
                Long.class))).isZero();
    }

    @Test
    void aDepartmentChangeWaitsForAnAssignmentInFlightAndThenRemovesIt() throws Exception {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        UUID d2 = department(owner, "Legal");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mover");
        patch("/api/v1/members/" + member.userId(), owner, Map.of("departmentId", d.toString()));

        // The assignment has read the membership under its lock and inserted the publisher row, not committed yet.
        CompletableFuture<ResponseEntity<JsonNode>> move = new CompletableFuture<>();
        asTenant(owner, () -> {
            jdbc.queryForList("SELECT user_id FROM core.memberships WHERE workspace_id = ? AND user_id = ? FOR SHARE",
                    UUID.class, owner.workspaceId(), member.userId());
            jdbc.update("INSERT INTO core.department_publishers (workspace_id, department_id, user_id) VALUES (?, ?, ?)",
                    owner.workspaceId(), d, member.userId());
            CompletableFuture.runAsync(() -> move.complete(
                    patch("/api/v1/members/" + member.userId(), owner, Map.of("departmentId", d2.toString()))));
            try {
                Thread.sleep(800);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            assertThat(move).as("the department change waits for the assignment").isNotDone();
            return null;
        });

        assertThat(move.get(10, TimeUnit.SECONDS).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.department_publishers",
                Long.class))).as("the row the assignment created is removed by the move").isZero();
    }

    @Test
    void aReassignmentWaitsForAWriteInFlight() throws Exception {
        Actor owner = newTeamWorkspace("own");
        UUID d = department(owner, "Finance");
        Actor a = addDepartmentPublisher(owner.workspaceId(), d, "pub-a");
        Actor b = addMember(owner.workspaceId(), "MEMBER", "pub-b");
        patch("/api/v1/members/" + b.userId(), owner, Map.of("departmentId", d.toString()));

        CompletableFuture<ResponseEntity<JsonNode>> reassignment = new CompletableFuture<>();
        asTenant(owner, () -> {
            // What an upload by A holds until it commits.
            jdbc.queryForList("SELECT user_id FROM core.department_publishers WHERE department_id = ? FOR SHARE",
                    UUID.class, d);
            CompletableFuture.runAsync(() -> reassignment.complete(
                    put("/api/v1/departments/" + d + "/publisher", owner, Map.of("userId", b.userId().toString()))));
            try {
                Thread.sleep(800);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            assertThat(reassignment).as("the reassignment waits for the write in flight").isNotDone();
            return null;
        });

        assertThat(reassignment.get(10, TimeUnit.SECONDS).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
    }
}
