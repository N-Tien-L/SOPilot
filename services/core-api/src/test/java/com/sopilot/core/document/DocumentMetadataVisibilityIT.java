package com.sopilot.core.document;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.outbox.OutboxEvent;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration tests for V2-24:
 * 1. Permission matrix ADR-007 §4.4 (OWNER/ADMIN/MEMBER in dept/MEMBER other dept/MEMBER no dept x WORKSPACE/DEPARTMENTS).
 * 2. Category lifecycle, unique name 409, archived restriction, delete sets document category null.
 * 3. Tags listing and auto-creation via PATCH/upload.
 * 4. Visibility change PUT with accessSync APPLIED/PENDING.
 * 5. Outbox ACCESS_UPDATED payload contract and retry/dead behavior.
 * 6. Race §7.1: pending INGEST_REQUESTED payload updated when visibility changes.
 */
class DocumentMetadataVisibilityIT extends ApiIT {

    private UUID createDepartment(Actor actor, String name) {
        ResponseEntity<JsonNode> created = post("/api/v1/departments", actor, Map.of("name", name));
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return id(created, "id");
    }

    private UUID createCategory(Actor actor, String name) {
        ResponseEntity<JsonNode> created = post("/api/v1/categories", actor, Map.of("name", name));
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        return id(created, "id");
    }

    @org.junit.jupiter.api.BeforeEach
    void cleanQueue() {
        dispatcher.dispatchDue();
        ai.reset();
    }

    private JsonNode data(ResponseEntity<JsonNode> response) {
        return response.getBody().path("data");
    }

    @Test
    void permissionMatrixWorkspaceVsDepartments() {
        Actor owner = newTeamWorkspace("own");
        UUID d1 = createDepartment(owner, "Finance");
        UUID d2 = createDepartment(owner, "Engineering");

        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");
        Actor memberD1 = addMember(owner.workspaceId(), "MEMBER", "mem-d1");
        Actor memberD2 = addMember(owner.workspaceId(), "MEMBER", "mem-d2");
        Actor memberNoDept = addMember(owner.workspaceId(), "MEMBER", "mem-none");
        Actor stranger = newTeamWorkspace("stranger");

        patch("/api/v1/members/" + memberD1.userId(), owner, Map.of("departmentId", d1.toString()));
        patch("/api/v1/members/" + memberD2.userId(), owner, Map.of("departmentId", d2.toString()));
        memberD1 = actorFor(memberD1.userId(), owner.workspaceId());
        memberD2 = actorFor(memberD2.userId(), owner.workspaceId());
        Actor financePublisher = addDepartmentPublisher(owner.workspaceId(), d1, "fin-pub");

        // Document 1: WORKSPACE visibility, written by the workspace publisher (the owner)
        UUID doc1 = id(uploadDocument(owner, "doc-workspace.md", markdown("workspace sop")), "id");

        // Document 2: DEPARTMENTS visibility (limited to Finance / D1), written by the Finance publisher
        UUID doc2 = id(uploadToDepartments(financePublisher, "doc-dept.md", markdown("dept sop"), d1), "id");

        // --- doc1 (WORKSPACE): Everyone in workspace sees it; stranger gets 404 ---
        for (Actor viewer : List.of(owner, admin, memberD1, memberD2, memberNoDept)) {
            assertThat(get("/api/v1/documents/" + doc1, viewer).getStatusCode()).isEqualTo(HttpStatus.OK);
            assertThat(get("/api/v1/documents/" + doc1 + "/download-url", viewer).getStatusCode()).isEqualTo(HttpStatus.OK);
        }
        assertThat(get("/api/v1/documents/" + doc1, stranger).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(get("/api/v1/documents/" + doc1 + "/download-url", stranger).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);

        // --- doc2 (DEPARTMENTS = [Finance/D1]): OWNER, ADMIN, and memberD1 see it; others 404 ---
        for (Actor authorized : List.of(owner, admin, memberD1)) {
            ResponseEntity<JsonNode> res = get("/api/v1/documents/" + doc2, authorized);
            assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
            assertThat(get("/api/v1/documents/" + doc2 + "/download-url", authorized).getStatusCode()).isEqualTo(HttpStatus.OK);
        }

        // memberD2 (wrong department), memberNoDept, and stranger MUST receive 404 (no leak of existence)
        for (Actor unauthorized : List.of(memberD2, memberNoDept, stranger)) {
            assertThat(get("/api/v1/documents/" + doc2, unauthorized).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
            assertThat(get("/api/v1/documents/" + doc2 + "/download-url", unauthorized).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        }

        // List verification: memberD2 and memberNoDept only see doc1
        JsonNode memberD2List = get("/api/v1/documents", memberD2).getBody().path("data");
        assertThat(memberD2List).hasSize(1);
        assertThat(memberD2List.get(0).path("id").asText()).isEqualTo(doc1.toString());

        JsonNode memberD1List = get("/api/v1/documents", memberD1).getBody().path("data");
        assertThat(memberD1List).hasSize(2);
    }

    @Test
    void changeVisibilityFlowAndAccessSyncAndAudit() throws Exception {
        Actor owner = newTeamWorkspace("own");
        UUID dept = createDepartment(owner, "Legal");
        UUID extra = createDepartment(owner, "Audit");
        Actor publisher = addDepartmentPublisher(owner.workspaceId(), dept, "legal-pub");
        UUID docId = id(uploadToDepartments(publisher, "legal-sop.md", markdown("legal"), dept), "id");

        // Document starts limited to Legal with accessRevision = 1
        JsonNode docBefore = data(get("/api/v1/documents/" + docId, owner));
        assertThat(docBefore.path("visibility").asText()).isEqualTo("DEPARTMENTS");
        assertThat(docBefore.path("departments")).hasSize(1);

        // The publisher widens the readers to Legal and Audit: same kind of document, owner department kept
        // (switching the kind is the OWNER's PUT /ownership, see DocumentPublisherIT)
        ResponseEntity<JsonNode> putRes = put("/api/v1/documents/" + docId + "/visibility", publisher,
                Map.of("visibility", "DEPARTMENTS", "departmentIds", List.of(dept.toString(), extra.toString())));

        assertThat(putRes.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(putRes.getBody().at("/data/accessSync").asText()).isEqualTo("APPLIED");

        // Check document DB state: visibility = DEPARTMENTS, accessRevision = 2
        JsonNode docAfter = data(get("/api/v1/documents/" + docId, owner));
        assertThat(docAfter.path("visibility").asText()).isEqualTo("DEPARTMENTS");
        assertThat(docAfter.path("departments")).hasSize(2);
        assertThat(docAfter.path("departments").toString()).contains(dept.toString(), extra.toString());

        // Check Outbox event ACCESS_UPDATED payload contract (§8)
        String payload = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT payload::text FROM core.outbox_events WHERE aggregate_id = ? AND event_type = 'ACCESS_UPDATED'",
                String.class, docId));
        JsonNode payloadJson = json.readTree(payload);
        assertThat(payloadJson.at("/visibility").asText()).isEqualTo("DEPARTMENTS");
        assertThat(payloadJson.at("/departmentIds/0").asText()).isEqualTo(dept.toString());
        assertThat(payloadJson.at("/accessRevision").asInt()).isEqualTo(2);
        assertThat(payloadJson.at("/workspaceId").asText()).isEqualTo(owner.workspaceId().toString());

        // Check audit log
        JsonNode audits = get("/api/v1/audit-logs?action=DOCUMENT_VISIBILITY_UPDATED", owner).getBody().path("data");
        assertThat(audits).hasSize(1);
    }

    @Test
    void changeVisibilityIsSentExactlyOnceWithATwoSecondTimeout() {
        Actor owner = newTeamWorkspace("own");
        UUID docId = id(uploadDocument(owner, "once.md", markdown("once")), "id");

        ResponseEntity<JsonNode> res = put("/api/v1/documents/" + docId + "/visibility", owner,
                Map.of("visibility", "WORKSPACE", "departmentIds", List.of()));

        assertThat(res.getBody().at("/data/accessSync").asText()).isEqualTo("APPLIED");
        assertThat(ai.sentOfType(OutboxEvent.Type.ACCESS_UPDATED)).isEqualTo(1);
        assertThat(ai.timeouts()).containsExactly(Duration.ofSeconds(2));
        assertThat(eventStatus(owner, docId, "ACCESS_UPDATED")).isEqualTo("DELIVERED");

        // A delivered event is never sent again, whether the dispatcher runs now or later.
        dispatcher.dispatchDue();
        makeDue(owner, docId);
        dispatcher.dispatchDue();
        assertThat(ai.sentOfType(OutboxEvent.Type.ACCESS_UPDATED)).isEqualTo(1);
    }

    @Test
    void changeVisibilityTimesOutYieldsPendingAndTheDispatcherDeliversItLater() {
        Actor owner = newTeamWorkspace("own");
        UUID docId = id(uploadDocument(owner, "doc.md", markdown("doc")), "id");

        // Simulate ai-service slower than the 2 s direct-send timeout.
        ai.delayResponses(2200);
        ResponseEntity<JsonNode> res;
        try {
            res = put("/api/v1/documents/" + docId + "/visibility", owner,
                    Map.of("visibility", "WORKSPACE", "departmentIds", List.of()));
        } finally {
            ai.delayResponses(0);
        }

        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(res.getBody().at("/data/accessSync").asText()).isEqualTo("PENDING");
        assertThat(eventStatus(owner, docId, "ACCESS_UPDATED")).isEqualTo("PENDING");
        assertThat(ai.sentOfType(OutboxEvent.Type.ACCESS_UPDATED)).isEqualTo(1);

        makeDue(owner, docId);
        dispatcher.dispatchDue();

        assertThat(eventStatus(owner, docId, "ACCESS_UPDATED")).isEqualTo("DELIVERED");
        List<OutboxEvent> access = ai.sent().stream().filter(e -> e.type() == OutboxEvent.Type.ACCESS_UPDATED).toList();
        assertThat(access).hasSize(2);
        assertThat(access.get(1).id()).as("same Idempotency-Key on the retry").isEqualTo(access.get(0).id());
    }

    @Test
    void raceConditionIngestVsAccessUpdate() throws Exception {
        Actor owner = newTeamWorkspace("own");
        UUID dept = createDepartment(owner, "Auditing");
        UUID extra = createDepartment(owner, "Compliance");
        Actor publisher = addDepartmentPublisher(owner.workspaceId(), dept, "audit-pub");

        // 1. Upload doc, creating INGEST_REQUESTED outbox event in PENDING state
        ResponseEntity<JsonNode> created = uploadToDepartments(publisher, "race.md", markdown("race"), dept);
        UUID docId = id(created, "id");

        // 2. Before dispatching INGEST_REQUESTED, the publisher widens the readers to a second department
        ResponseEntity<JsonNode> visRes = put("/api/v1/documents/" + docId + "/visibility", publisher,
                Map.of("visibility", "DEPARTMENTS", "departmentIds", List.of(dept.toString(), extra.toString())));
        assertThat(visRes.getStatusCode()).isEqualTo(HttpStatus.OK);

        // 3. Race §7.1 check: verify that the pending INGEST_REQUESTED event has its access updated!
        String ingestPayload = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT payload::text FROM core.outbox_events WHERE aggregate_id = ? AND event_type = 'INGEST_REQUESTED'",
                String.class, docId));
        JsonNode p = json.readTree(ingestPayload);
        assertThat(p.at("/access/visibility").asText()).isEqualTo("DEPARTMENTS");
        assertThat(p.at("/access/departmentIds/0").asText()).isEqualTo(dept.toString());
        assertThat(p.at("/access/departmentIds")).hasSize(2);
        assertThat(p.at("/access/accessRevision").asInt()).isEqualTo(2);

        // 4. Dispatch events: INGEST_REQUESTED will be delivered with the new access state!
        dispatcher.dispatchDue();
        List<OutboxEvent> ingests = ai.sent().stream().filter(e -> e.type() == OutboxEvent.Type.INGEST_REQUESTED).toList();
        assertThat(ingests).hasSize(1);
        JsonNode sentAccess = json.readTree(ingests.get(0).payload()).path("access");
        assertThat(sentAccess.path("visibility").asText()).isEqualTo("DEPARTMENTS");
        assertThat(sentAccess.at("/departmentIds/0").asText()).isEqualTo(dept.toString());
        assertThat(sentAccess.path("departmentIds")).hasSize(2);
        assertThat(sentAccess.path("accessRevision").asInt()).isEqualTo(2);
    }

    @Test
    void categoryLifecycleAndArchivedRestrictions() {
        Actor owner = newTeamWorkspace("own");
        Actor other = newTeamWorkspace("other");

        // 1. Unique category name per workspace (case-insensitive) -> 409
        UUID catId = createCategory(owner, "Chính sách");
        assertThat(post("/api/v1/categories", owner, Map.of("name", "  chính SÁCH ")).getStatusCode())
                .isEqualTo(HttpStatus.CONFLICT);
        createCategory(other, "Chính sách"); // OK in other workspace

        // 2. Members can list categories
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        assertThat(get("/api/v1/categories", member).getBody().path("data")).hasSize(1);

        // 3. Assign category via PATCH
        UUID docId = id(uploadDocument(owner, "doc.md", markdown("doc")), "id");
        ResponseEntity<JsonNode> patched = patch("/api/v1/documents/" + docId, owner,
                Map.of("categoryId", catId.toString(), "tags", List.of("tag1", "tag2")));
        assertThat(patched.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(data(patched).at("/category/id").asText()).isEqualTo(catId.toString());
        assertThat(data(patched).at("/category/name").asText()).isEqualTo("Chính sách");
        assertThat(data(patched).at("/fieldSources/category").asText()).isEqualTo("USER");
        assertThat(data(patched).at("/fieldSources/tags").asText()).isEqualTo("USER");

        // 4. Archive category: cannot assign newly
        patch("/api/v1/categories/" + catId, owner, Map.of("status", "ARCHIVED"));
        UUID doc2 = id(uploadDocument(owner, "doc2.md", markdown("doc2")), "id");
        assertThat(patch("/api/v1/documents/" + doc2, owner, Map.of("categoryId", catId.toString())).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);

        // 5. Delete category: document's category becomes null without affecting permissions
        delete("/api/v1/categories/" + catId, owner);
        JsonNode docAfterDelete = data(get("/api/v1/documents/" + docId, owner));
        assertThat(docAfterDelete.path("category").isNull()).isTrue();
        assertThat(get("/api/v1/documents/" + docId, member).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void tagsListingAndCreation() {
        Actor owner = newTeamWorkspace("own");
        UUID docId = id(uploadDocument(owner, "doc.md", markdown("doc")), "id");

        assertThat(get("/api/v1/tags", owner).getBody().path("data")).isEmpty();

        // Attach tags via PATCH
        patch("/api/v1/documents/" + docId, owner, Map.of("tags", List.of("ISO", "Quy trình")));

        JsonNode tags = get("/api/v1/tags", owner).getBody().path("data");
        assertThat(tags).hasSize(2);

        // Filter documents by tag
        JsonNode filtered = get("/api/v1/documents?tag=iso", owner).getBody().path("data");
        assertThat(filtered).hasSize(1);
    }

    @Test
    void duplicateDepartmentIdsAreDeduplicatedOnUploadAndVisibilityChange() {
        Actor owner = newTeamWorkspace("own");
        UUID d1 = createDepartment(owner, "Finance");
        UUID d2 = createDepartment(owner, "Legal");
        Actor publisher = addDepartmentPublisher(owner.workspaceId(), d1, "fin-pub");

        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("visibility", "DEPARTMENTS");
        params.add("departmentIds", d1.toString());
        params.add("departmentIds", d1.toString());
        ResponseEntity<JsonNode> created = upload("/api/v1/documents", publisher, "dup.md", markdown("dup"), params);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(data(created).path("departments")).hasSize(1);
        UUID docId = id(created, "id");

        ResponseEntity<JsonNode> changed = put("/api/v1/documents/" + docId + "/visibility", publisher,
                Map.of("visibility", "DEPARTMENTS", "departmentIds",
                        List.of(d2.toString(), d1.toString(), d2.toString(), d1.toString())));
        assertThat(changed.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(data(get("/api/v1/documents/" + docId, owner)).path("departments")).hasSize(2);
        String payload = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT payload::text FROM core.outbox_events WHERE aggregate_id = ? AND event_type = 'ACCESS_UPDATED'",
                String.class, docId));
        assertThat(payload).contains(d2.toString(), d1.toString());
        assertThat(payload.split(d1.toString(), -1)).as("each department once").hasSize(2);
    }

    @Test
    void uploadAcceptsAnOptionalTitleThatBecomesAUserTitleAndIsSentToAiService() throws Exception {
        Actor owner = newTeamWorkspace("own");

        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("title", "  Quy trình mua hàng  ");
        ResponseEntity<JsonNode> titled = upload("/api/v1/documents", owner, "file-name.md", markdown("titled"), params);
        assertThat(titled.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(data(titled).path("title").asText()).isEqualTo("Quy trình mua hàng");
        assertThat(data(titled).at("/fieldSources/title").asText()).isEqualTo("USER");

        ResponseEntity<JsonNode> plain = uploadDocument(owner, "plain-name.md", markdown("plain"));
        assertThat(data(plain).path("title").asText()).isEqualTo("plain-name");
        assertThat(data(plain).at("/fieldSources/title").asText()).isEqualTo("SYSTEM");

        dispatcher.dispatchDue();
        UUID titledId = id(titled, "id");
        OutboxEvent ingest = ai.sent().stream()
                .filter(e -> e.type() == OutboxEvent.Type.INGEST_REQUESTED && e.aggregateId().equals(titledId))
                .findFirst().orElseThrow();
        assertThat(json.readTree(ingest.payload()).path("title").asText()).isEqualTo("Quy trình mua hàng");

        for (String bad : List.of("   ", "x".repeat(201))) {
            MultiValueMap<String, String> invalid = new LinkedMultiValueMap<>();
            invalid.add("title", bad);
            assertThat(upload("/api/v1/documents", owner, "bad.md", markdown("bad"), invalid).getStatusCode())
                    .isEqualTo(HttpStatus.BAD_REQUEST);
        }
    }

    @Test
    void departmentValidationOnVisibilityChange() {
        Actor owner = newTeamWorkspace("own");
        Actor other = newTeamWorkspace("other");
        UUID otherDept = createDepartment(other, "OtherDept");
        UUID archivedDept = createDepartment(owner, "ArchivedDept");
        patch("/api/v1/departments/" + archivedDept, owner, Map.of("status", "ARCHIVED"));

        UUID docId = id(uploadDocument(owner, "doc.md", markdown("doc")), "id");

        // 1. Empty departmentIds for DEPARTMENTS -> 400
        assertThat(put("/api/v1/documents/" + docId + "/visibility", owner,
                Map.of("visibility", "DEPARTMENTS", "departmentIds", List.of())).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);

        // 2. Department from another workspace -> 400
        assertThat(put("/api/v1/documents/" + docId + "/visibility", owner,
                Map.of("visibility", "DEPARTMENTS", "departmentIds", List.of(otherDept.toString()))).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);

        // 3. ARCHIVED department -> 400
        assertThat(put("/api/v1/documents/" + docId + "/visibility", owner,
                Map.of("visibility", "DEPARTMENTS", "departmentIds", List.of(archivedDept.toString()))).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void outboxRetryOn5xxAndDeadOn4xx() {
        Actor owner = newTeamWorkspace("own");
        UUID docId = id(uploadDocument(owner, "doc.md", markdown("doc")), "id");

        // 5xx from ai-service causes retry, then success
        ai.respondWith(500, 200);
        dispatcher.dispatchDue(); // sends 500, marked for retry
        makeDue(owner, docId);
        dispatcher.dispatchDue(); // sends 200, marked DELIVERED
        assertThat(asTenant(owner, () -> jdbc.queryForObject(
                "SELECT status FROM core.outbox_events WHERE aggregate_id = ? AND event_type = 'INGEST_REQUESTED'",
                String.class, docId))).isEqualTo("DELIVERED");

        // Visibility update with 400 from ai-service goes DEAD immediately
        ai.alwaysRespondWith(400);
        put("/api/v1/documents/" + docId + "/visibility", owner, Map.of("visibility", "WORKSPACE"));
        assertThat(asTenant(owner, () -> jdbc.queryForObject(
                "SELECT status FROM core.outbox_events WHERE aggregate_id = ? AND event_type = 'ACCESS_UPDATED'",
                String.class, docId))).isEqualTo("DEAD");
    }

    private String eventStatus(Actor ws, UUID document, String type) {
        return asTenant(ws, () -> jdbc.queryForObject(
                "SELECT status FROM core.outbox_events WHERE aggregate_id = ? AND event_type = ?",
                String.class, document, type));
    }

    private void makeDue(Actor ws, UUID document) {
        asTenant(ws, () -> jdbc.update("UPDATE core.outbox_events SET next_attempt_at = now() - interval '1 second' "
                + "WHERE aggregate_id = ? AND status = 'PENDING'", document));
    }
}
