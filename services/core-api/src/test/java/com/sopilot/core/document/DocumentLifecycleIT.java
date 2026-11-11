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

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** V2-12: upload validation, outbox, version rules, retry, status callbacks, delete (TECH §3.3, §5.5, §8). */
class DocumentLifecycleIT extends ApiIT {

    // ---- helpers ----------------------------------------------------------------------------------

    private ResponseEntity<JsonNode> callback(UUID workspaceId, UUID documentId, UUID versionId, String token,
                                              Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (token != null) {
            headers.set("X-Internal-Token", token);
        }
        Map<String, Object> full = new LinkedHashMap<>(body);
        full.put("workspaceId", workspaceId.toString());
        return http.exchange("/internal/documents/" + documentId + "/versions/" + versionId + "/status",
                HttpMethod.PATCH, new HttpEntity<>(full, headers), JsonNode.class);
    }

    private ResponseEntity<JsonNode> report(Actor ws, UUID doc, UUID ver, String status, int attempt) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", status);
        body.put("attempt", attempt);
        if ("READY".equals(status)) {
            body.put("pageCount", 7);
            body.put("detectedLanguage", "vi");
            body.put("chunkCount", 41);
            body.put("embedding", Map.of("provider", "local", "model", "BAAI/bge-m3", "revision", "abc", "dim", 1024));
            body.put("extracted", Map.of("docCode", "QT-MH-01", "revisionLabel", "03", "effectiveDate", "2026-01-15"));
            body.put("warningCodes", List.of("PAGES_WITHOUT_TEXT"));
        }
        return callback(ws.workspaceId(), doc, ver, "test-internal-token", body);
    }

    private ResponseEntity<JsonNode> fail(Actor ws, UUID doc, UUID ver, String code, int attempt) {
        return callback(ws.workspaceId(), doc, ver, "test-internal-token", Map.of("status", "FAILED",
                "attempt", attempt, "failureCode", code, "failureMessage", "boom: java.lang.NullPointerException at X"));
    }

    private long outboxCount(Actor ws, UUID doc, OutboxEvent.Type type) {
        return asTenant(ws, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events WHERE aggregate_id = ? "
                + "AND event_type = ?", Long.class, doc, type.name()));
    }

    private long versionCount(Actor ws, UUID doc) {
        return asTenant(ws, () -> jdbc.queryForObject("SELECT count(*) FROM core.document_versions WHERE document_id = ?",
                Long.class, doc));
    }

    private String versionStatus(Actor ws, UUID version) {
        return asTenant(ws, () -> jdbc.queryForObject("SELECT status FROM core.document_versions WHERE id = ?",
                String.class, version));
    }

    private JsonNode data(ResponseEntity<JsonNode> response) {
        return response.getBody().path("data");
    }

    /** Uploads and walks the version to READY. */
    private UUID readyDocument(Actor ws, String name) {
        ResponseEntity<JsonNode> created = uploadDocument(ws, name, markdown(name));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");
        report(ws, doc, ver, "PROCESSING", 0);
        report(ws, doc, ver, "READY", 0);
        return doc;
    }

    // ---- upload -----------------------------------------------------------------------------------

    @Test
    void uploadStoresTheFileWritesOneOutboxEventAndAuditsIt() throws Exception {
        Actor owner = newTeamWorkspace("own");
        byte[] content = markdown("Quy trình mua hàng");

        ResponseEntity<JsonNode> created = uploadDocument(owner, "QT-MH-01.md", content);

        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        JsonNode doc = data(created);
        assertThat(doc.path("title").asText()).isEqualTo("QT-MH-01");
        assertThat(doc.path("status").asText()).isEqualTo("UPLOADED");
        assertThat(doc.path("answerable").asBoolean()).isFalse();
        assertThat(doc.path("visibility").asText()).isEqualTo("WORKSPACE");
        UUID docId = UUID.fromString(doc.path("id").asText());
        UUID verId = UUID.fromString(doc.at("/latestVersion/id").asText());
        String key = "workspaces/" + owner.workspaceId() + "/documents/" + docId + "/versions/" + verId;
        assertThat(storage.get(key)).isEqualTo(content);

        assertThat(outboxCount(owner, docId, OutboxEvent.Type.INGEST_REQUESTED)).isEqualTo(1);
        String payload = asTenant(owner, () -> jdbc.queryForObject("SELECT payload::text FROM core.outbox_events "
                + "WHERE aggregate_id = ?", String.class, docId));
        JsonNode p = json.readTree(payload);
        assertThat(p.path("objectKey").asText()).isEqualTo(key);
        assertThat(p.path("attempt").asInt()).isZero();
        assertThat(p.path("versionNo").asInt()).isEqualTo(1);
        assertThat(p.path("fileType").asText()).isEqualTo("MD");
        assertThat(p.path("sha256").asText()).hasSize(64);
        assertThat(p.at("/access/visibility").asText()).isEqualTo("WORKSPACE");
        assertThat(p.at("/access/accessRevision").asInt()).isEqualTo(1);
        assertThat(p.at("/suggest/enabled").asBoolean()).isFalse();

        assertThat(get("/api/v1/audit-logs?action=DOCUMENT_UPLOADED", owner).getBody().path("data")).hasSize(1);
    }

    @Test
    void onlyThePublisherMayWriteButEveryMemberCanReadAndDownload() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        Actor admin = addMember(owner.workspaceId(), "ADMIN", "adm");
        UUID doc = id(uploadDocument(owner, "a.md", markdown("a")), "id");

        // ADMIN is not the workspace publisher either (ADR-009); the full matrix is DocumentPublisherIT.
        for (Actor refused : List.of(member, admin)) {
            ResponseEntity<JsonNode> upload = uploadDocument(refused, "b.md", markdown("b"));
            assertThat(upload.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
            assertThat(upload.getBody().at("/error/code").asText()).isEqualTo("NOT_PUBLISHER");
            assertThat(post("/api/v1/documents/" + doc + "/retry", refused, null).getStatusCode())
                    .isEqualTo(HttpStatus.FORBIDDEN);
            assertThat(patch("/api/v1/documents/" + doc, refused, Map.of("title", "x")).getStatusCode())
                    .isEqualTo(HttpStatus.FORBIDDEN);
        }
        assertThat(delete("/api/v1/documents/" + doc, member).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(get("/api/v1/documents/" + doc + "/versions", member).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);

        assertThat(get("/api/v1/documents/" + doc, member).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(get("/api/v1/documents", member).getBody().path("data")).hasSize(1);
        JsonNode url = data(get("/api/v1/documents/" + doc + "/download-url", member));
        assertThat(url.path("url").asText()).startsWith("http://storage.test/workspaces/");
        assertThat(url.path("expiresAt").asText()).isNotBlank();
    }

    @Test
    void unsupportedFilesAreRefusedWith415AndLeaveNoTrace() {
        Actor owner = newTeamWorkspace("own");

        Map<String, byte[]> files = new LinkedHashMap<>();
        files.put("notes.txt", markdown("txt"));
        files.put("report.docx", new byte[] {'P', 'K', 3, 4, 1});
        files.put("scan.png", new byte[] {(byte) 0x89, 'P', 'N', 'G'});
        files.put("fake.pdf", markdown("not a pdf"));
        files.put("binary.md", new byte[] {'#', ' ', 'a', 0, 'b'});
        for (Map.Entry<String, byte[]> f : files.entrySet()) {
            ResponseEntity<JsonNode> r = uploadDocument(owner, f.getKey(), f.getValue());
            assertThat(r.getStatusCode()).as(f.getKey()).isEqualTo(HttpStatus.UNSUPPORTED_MEDIA_TYPE);
            assertThat(r.getBody().at("/error/code").asText()).as(f.getKey()).isEqualTo("UNSUPPORTED_TYPE");
        }
        assertThat(uploadDocument(owner, "x.txt", markdown("t")).getBody().at("/error/message").asText())
                .contains(".md");
        assertThat(uploadDocument(owner, "x.docx", markdown("t")).getBody().at("/error/message").asText())
                .contains("PDF");

        ResponseEntity<JsonNode> latin1 = uploadDocument(owner, "latin.md", "café menu".getBytes(StandardCharsets.ISO_8859_1));
        assertThat(latin1.getStatusCode()).isEqualTo(HttpStatus.UNSUPPORTED_MEDIA_TYPE);
        assertThat(latin1.getBody().at("/error/code").asText()).isEqualTo("INVALID_ENCODING");

        assertThat(storage.count()).isZero();
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.documents", Long.class))).isZero();
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events", Long.class))).isZero();
    }

    @Test
    void emptyAndOversizedFilesAreRejected() {
        Actor owner = newTeamWorkspace("own");

        assertThat(uploadDocument(owner, "empty.md", new byte[0]).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        byte[] big = new byte[20 * 1024 * 1024 + 1];
        big[0] = '#';
        ResponseEntity<JsonNode> r = uploadDocument(owner, "big.md", big);
        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.PAYLOAD_TOO_LARGE);
        assertThat(r.getBody().at("/error/code").asText()).isEqualTo("FILE_TOO_LARGE");
        assertThat(storage.count()).isZero();
    }

    @Test
    void identicalBytesAreADuplicateInTheSameWorkspaceOnly() {
        Actor owner = newTeamWorkspace("own");
        Actor stranger = newTeamWorkspace("stranger");
        byte[] content = markdown("Same file");

        UUID first = id(uploadDocument(owner, "first.md", content), "id");
        ResponseEntity<JsonNode> again = uploadDocument(owner, "renamed.md", content);

        assertThat(again.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(again.getBody().at("/error/code").asText()).isEqualTo("DUPLICATE_DOCUMENT");
        assertThat(again.getBody().at("/error/details/documentId").asText()).isEqualTo(first.toString());
        assertThat(again.getBody().at("/error/details/title").asText()).isEqualTo("first");
        assertThat(uploadDocument(stranger, "first.md", content).getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(storage.count()).isEqualTo(2);
    }

    @Test
    void storageFailureRollsTheUploadBackCompletely() {
        Actor owner = newTeamWorkspace("own");
        storage.failPuts(true);

        ResponseEntity<JsonNode> r = uploadDocument(owner, "a.md", markdown("a"));

        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.documents", Long.class))).isZero();
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events", Long.class))).isZero();
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.audit_logs WHERE action = 'DOCUMENT_UPLOADED'",
                Long.class))).isZero();
    }

    // ---- status callbacks -------------------------------------------------------------------------

    @Test
    void readyCallbackActivatesTheVersionAndStoresWhatWasExtracted() {
        Actor owner = newTeamWorkspace("own");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", markdown("sop"));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");

        assertThat(report(owner, doc, ver, "PROCESSING", 0).getBody().path("applied").asBoolean()).isTrue();
        assertThat(data(get("/api/v1/documents/" + doc, owner)).path("status").asText()).isEqualTo("PROCESSING");
        assertThat(report(owner, doc, ver, "READY", 0).getStatusCode()).isEqualTo(HttpStatus.OK);

        JsonNode d = data(get("/api/v1/documents/" + doc, owner));
        assertThat(d.path("status").asText()).isEqualTo("READY");
        assertThat(d.path("answerable").asBoolean()).isTrue();
        assertThat(d.path("language").asText()).isEqualTo("vi");
        assertThat(d.at("/currentVersion/id").asText()).isEqualTo(ver.toString());
        assertThat(d.at("/currentVersion/pageCount").asInt()).isEqualTo(7);
        assertThat(d.at("/currentVersion/docCode").asText()).isEqualTo("QT-MH-01");
        assertThat(d.at("/currentVersion/revisionLabel").asText()).isEqualTo("03");
        assertThat(d.at("/currentVersion/effectiveDate").asText()).isEqualTo("2026-01-15");
        assertThat(d.at("/currentVersion/warningCodes/0").asText()).isEqualTo("PAGES_WITHOUT_TEXT");
        // Repeating the callback is harmless.
        assertThat(report(owner, doc, ver, "READY", 0).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void invalidTransitionsAreConflictsAndInternalRoutesNeedTheToken() {
        Actor owner = newTeamWorkspace("own");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", markdown("sop"));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");
        report(owner, doc, ver, "PROCESSING", 0);
        fail(owner, doc, ver, "NO_TEXT_LAYER", 0);

        ResponseEntity<JsonNode> badMove = callback(owner.workspaceId(), doc, ver, "test-internal-token",
                Map.of("status", "UPLOADED", "attempt", 0));
        assertThat(badMove.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(callback(owner.workspaceId(), doc, UUID.randomUUID(), "test-internal-token",
                Map.of("status", "PROCESSING", "attempt", 0)).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);

        Map<String, Object> processing = Map.of("status", "PROCESSING", "attempt", 0);
        assertThat(callback(owner.workspaceId(), doc, ver, null, processing).getStatusCode())
                .isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(callback(owner.workspaceId(), doc, ver, "wrong", processing).getStatusCode())
                .isEqualTo(HttpStatus.UNAUTHORIZED);
        // A browser token is not an internal token.
        assertThat(callback(owner.workspaceId(), doc, ver, owner.token(), processing).getStatusCode())
                .isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void aCallbackForAnotherWorkspaceCannotTouchTheVersion() {
        Actor owner = newTeamWorkspace("own");
        Actor stranger = newTeamWorkspace("stranger");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", markdown("sop"));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");

        ResponseEntity<JsonNode> r = report(stranger, doc, ver, "PROCESSING", 0);

        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(versionStatus(owner, ver)).isEqualTo("UPLOADED");
    }

    // ---- replacing versions -----------------------------------------------------------------------

    @Test
    void whileAVersionIsProcessingTheSameBytesAreRecognisedAndOtherBytesAreRefused() {
        Actor owner = newTeamWorkspace("own");
        byte[] content = markdown("v1");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", content);
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");
        long outbox = outboxCount(owner, doc, OutboxEvent.Type.INGEST_REQUESTED);

        ResponseEntity<JsonNode> repeat = upload("/api/v1/documents/" + doc + "/versions", owner, "sop.md", content);
        assertThat(repeat.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(data(repeat).at("/latestVersion/id").asText()).isEqualTo(ver.toString());

        ResponseEntity<JsonNode> other = upload("/api/v1/documents/" + doc + "/versions", owner, "sop.md", markdown("v2"));
        assertThat(other.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(other.getBody().at("/error/code").asText()).isEqualTo("VERSION_IN_PROGRESS");

        report(owner, doc, ver, "PROCESSING", 0);
        assertThat(upload("/api/v1/documents/" + doc + "/versions", owner, "sop.md", markdown("v3")).getBody()
                .at("/error/code").asText()).isEqualTo("VERSION_IN_PROGRESS");

        assertThat(versionCount(owner, doc)).isEqualTo(1);
        assertThat(outboxCount(owner, doc, OutboxEvent.Type.INGEST_REQUESTED)).isEqualTo(outbox);
        assertThat(storage.count()).isEqualTo(1);
    }

    @Test
    void theCurrentBytesAreAnUnchangedDocumentAndOtherDocumentsBytesAreADuplicate() {
        Actor owner = newTeamWorkspace("own");
        byte[] content = markdown("v1");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", content);
        UUID doc = id(created, "id");
        report(owner, doc, id(created, "latestVersion", "id"), "PROCESSING", 0);
        report(owner, doc, id(created, "latestVersion", "id"), "READY", 0);
        byte[] other = markdown("other doc");
        uploadDocument(owner, "other.md", other);
        long outbox = outboxCount(owner, doc, OutboxEvent.Type.INGEST_REQUESTED);

        ResponseEntity<JsonNode> unchanged = upload("/api/v1/documents/" + doc + "/versions", owner, "sop.md", content);
        assertThat(unchanged.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(unchanged.getBody().at("/error/code").asText()).isEqualTo("DOCUMENT_UNCHANGED");

        ResponseEntity<JsonNode> duplicate = upload("/api/v1/documents/" + doc + "/versions", owner, "sop.md", other);
        assertThat(duplicate.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(duplicate.getBody().at("/error/code").asText()).isEqualTo("DUPLICATE_DOCUMENT");

        assertThat(versionCount(owner, doc)).isEqualTo(1);
        assertThat(outboxCount(owner, doc, OutboxEvent.Type.INGEST_REQUESTED)).isEqualTo(outbox);
    }

    @Test
    void aNewVersionKeepsTheOldOneServingUntilItIsReadyThenSupersedesEverythingOlder() {
        Actor owner = newTeamWorkspace("own");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", markdown("v1"));
        UUID doc = id(created, "id");
        UUID v1 = id(created, "latestVersion", "id");
        report(owner, doc, v1, "PROCESSING", 0);
        report(owner, doc, v1, "READY", 0);
        String v1Key = asTenant(owner, () -> jdbc.queryForObject("SELECT object_key FROM core.document_versions WHERE id = ?",
                String.class, v1));

        // v2 fails: v1 is still the current, answerable version.
        ResponseEntity<JsonNode> second = upload("/api/v1/documents/" + doc + "/versions", owner, "sop.md", markdown("v2"));
        assertThat(second.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        UUID v2 = id(second, "latestVersion", "id");
        assertThat(data(second).at("/latestVersion/versionNo").asInt()).isEqualTo(2);
        assertThat(data(second).at("/currentVersion/id").asText()).isEqualTo(v1.toString());
        assertThat(data(second).path("answerable").asBoolean()).isTrue();
        report(owner, doc, v2, "PROCESSING", 0);
        fail(owner, doc, v2, "EMBEDDING_ERROR", 0);
        JsonNode afterFailure = data(get("/api/v1/documents/" + doc, owner));
        assertThat(afterFailure.path("status").asText()).isEqualTo("FAILED");
        assertThat(afterFailure.at("/currentVersion/id").asText()).isEqualTo(v1.toString());
        assertThat(afterFailure.path("answerable").asBoolean()).isTrue();
        assertThat(storage.has(v1Key)).isTrue();

        // v3 reaches READY: both older versions, the FAILED one included, become SUPERSEDED.
        ResponseEntity<JsonNode> third = upload("/api/v1/documents/" + doc + "/versions", owner, "sop.md", markdown("v3"));
        UUID v3 = id(third, "latestVersion", "id");
        report(owner, doc, v3, "PROCESSING", 0);
        report(owner, doc, v3, "READY", 0);

        assertThat(versionStatus(owner, v1)).isEqualTo("SUPERSEDED");
        assertThat(versionStatus(owner, v2)).isEqualTo("SUPERSEDED");
        assertThat(versionStatus(owner, v3)).isEqualTo("READY");
        assertThat(data(get("/api/v1/documents/" + doc, owner)).at("/currentVersion/id").asText()).isEqualTo(v3.toString());
        assertThat(storage.has(v1Key)).as("superseded file is deleted").isFalse();
        assertThat(data(get("/api/v1/documents/" + doc + "/versions", owner))).hasSize(3);
        assertThat(get("/api/v1/audit-logs?action=DOCUMENT_VERSION_UPLOADED", owner).getBody().path("data")).hasSize(2);
    }

    // ---- retry -----------------------------------------------------------------------------------

    @Test
    void retryIncrementsTheAttemptOncePerFailureAndStaleCallbacksAreIgnored() throws Exception {
        Actor owner = newTeamWorkspace("own");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", markdown("sop"));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");
        UUID untouched = id(uploadDocument(owner, "other.md", markdown("other")), "id");

        assertThat(post("/api/v1/documents/" + doc + "/retry", owner, null).getBody().at("/error/code").asText())
                .isEqualTo("VERSION_NOT_FAILED");

        report(owner, doc, ver, "PROCESSING", 0);
        fail(owner, doc, ver, "NO_TEXT_LAYER", 0);
        JsonNode failed = data(get("/api/v1/documents/" + doc, owner));
        assertThat(failed.at("/latestVersion/failureCode").asText()).isEqualTo("NO_TEXT_LAYER");
        // The message is the fixed sentence for the code, never what ai-service sent.
        assertThat(failed.at("/latestVersion/failureMessage").asText()).contains("lớp chữ").doesNotContain("NullPointer");

        ResponseEntity<JsonNode> retried = post("/api/v1/documents/" + doc + "/retry", owner, null);
        assertThat(retried.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(data(retried).at("/latestVersion/status").asText()).isEqualTo("UPLOADED");
        assertThat(data(retried).at("/latestVersion/failureCode").isNull()).isTrue();
        assertThat(outboxCount(owner, doc, OutboxEvent.Type.INGEST_REQUESTED)).isEqualTo(2);
        List<String> payloads = asTenant(owner, () -> jdbc.queryForList("SELECT payload::text FROM core.outbox_events "
                + "WHERE aggregate_id = ? ORDER BY created_at, id", String.class, doc));
        assertThat(json.readTree(payloads.get(1)).path("attempt").asInt()).isEqualTo(1);
        assertThat(json.readTree(payloads.get(1)).path("versionId").asText()).isEqualTo(ver.toString());

        // Pressing the button twice creates only one job.
        assertThat(post("/api/v1/documents/" + doc + "/retry", owner, null).getBody().at("/error/code").asText())
                .isEqualTo("VERSION_NOT_FAILED");
        assertThat(outboxCount(owner, doc, OutboxEvent.Type.INGEST_REQUESTED)).isEqualTo(2);

        // A late callback of the first attempt changes nothing; the new attempt proceeds.
        ResponseEntity<JsonNode> stale = fail(owner, doc, ver, "CORRUPT_FILE", 0);
        assertThat(stale.getBody().path("applied").asBoolean()).isFalse();
        assertThat(versionStatus(owner, ver)).isEqualTo("UPLOADED");
        report(owner, doc, ver, "PROCESSING", 1);
        report(owner, doc, ver, "READY", 1);
        assertThat(data(get("/api/v1/documents/" + doc, owner)).path("answerable").asBoolean()).isTrue();

        // Retrying one file never touched the other document.
        assertThat(outboxCount(owner, untouched, OutboxEvent.Type.INGEST_REQUESTED)).isEqualTo(1);
        assertThat(data(get("/api/v1/documents/" + untouched, owner)).path("status").asText()).isEqualTo("UPLOADED");
    }

    @Test
    void failureDetailsAreForManagersOnly() {
        Actor owner = newTeamWorkspace("own");
        Actor member = addMember(owner.workspaceId(), "MEMBER", "mem");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "sop.md", markdown("sop"));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");
        report(owner, doc, ver, "PROCESSING", 0);
        fail(owner, doc, ver, "ENCRYPTED_PDF", 0);

        JsonNode asMember = data(get("/api/v1/documents/" + doc, member));
        assertThat(asMember.path("status").asText()).isEqualTo("FAILED");
        assertThat(asMember.at("/latestVersion/failureCode").isNull()).isTrue();
        assertThat(asMember.at("/latestVersion/failureMessage").isNull()).isTrue();
    }

    // ---- edit, delete, dispatch -------------------------------------------------------------------

    @Test
    void editingTitleAndDescriptionNeverCreatesAnIngestionEvent() {
        Actor owner = newTeamWorkspace("own");
        UUID doc = readyDocument(owner, "sop.md");
        long before = asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events", Long.class));

        ResponseEntity<JsonNode> edited = patch("/api/v1/documents/" + doc, owner,
                Map.of("title", "Quy trình mới", "description", "Mô tả"));

        assertThat(data(edited).path("title").asText()).isEqualTo("Quy trình mới");
        assertThat(data(edited).path("description").asText()).isEqualTo("Mô tả");
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events", Long.class)))
                .isEqualTo(before);
        assertThat(patch("/api/v1/documents/" + doc, owner, Map.of("title", " ")).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(patch("/api/v1/documents/" + doc, owner, Map.of("visibility", "WORKSPACE")).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void deleteHidesTheDocumentAtOnceAndRemovesFilesAndRowsWhenAiServiceConfirms() {
        Actor owner = newTeamWorkspace("own");
        byte[] content = markdown("gone");
        UUID doc = id(uploadDocument(owner, "gone.md", content), "id");
        dispatcher.dispatchDue();

        assertThat(delete("/api/v1/documents/" + doc, owner).getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        assertThat(get("/api/v1/documents/" + doc, owner).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(get("/api/v1/documents", owner).getBody().path("data")).isEmpty();
        assertThat(outboxCount(owner, doc, OutboxEvent.Type.DOCUMENT_DELETED)).isEqualTo(1);
        // Soft-deleted: the bytes may be uploaded again right away, and it no longer counts for the quota.
        assertThat(uploadDocument(owner, "again.md", content).getStatusCode()).isEqualTo(HttpStatus.CREATED);

        dispatcher.dispatchDue();

        // Other test classes share the database, so look only at this workspace's events.
        assertThat(ai.sent().stream().filter(e -> e.workspaceId().equals(owner.workspaceId())
                && e.type() == OutboxEvent.Type.DOCUMENT_DELETED)).hasSize(1);
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.documents WHERE id = ?",
                Long.class, doc))).isZero();
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.document_versions WHERE document_id = ?",
                Long.class, doc))).isZero();
        assertThat(storage.list("workspaces/" + owner.workspaceId() + "/documents/" + doc, 10)).isEmpty();
        assertThat(storage.count()).isEqualTo(1);
    }

    @Test
    void anotherWorkspaceCannotSeeOrChangeTheDocument() {
        Actor owner = newTeamWorkspace("own");
        Actor stranger = newTeamWorkspace("stranger");
        UUID doc = id(uploadDocument(owner, "sop.md", markdown("sop")), "id");

        assertThat(get("/api/v1/documents/" + doc, stranger).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(get("/api/v1/documents/" + doc + "/download-url", stranger).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(delete("/api/v1/documents/" + doc, stranger).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(post("/api/v1/documents/" + doc + "/retry", stranger, null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(upload("/api/v1/documents/" + doc + "/versions", stranger, "x.md", markdown("x")).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(get("/api/v1/documents", stranger).getBody().path("data")).isEmpty();
    }

    @Test
    void listIsPagedNewestFirstAndFilteredByStatusAndTitle() {
        Actor owner = newTeamWorkspace("own");
        for (int i = 1; i <= 5; i++) {
            uploadDocument(owner, "doc" + i + ".md", markdown("doc" + i));
        }
        UUID ready = readyDocument(owner, "ready-one.md");

        JsonNode page1 = get("/api/v1/documents?limit=4", owner).getBody();
        assertThat(page1.path("data")).hasSize(4);
        assertThat(page1.at("/page/hasMore").asBoolean()).isTrue();
        assertThat(page1.at("/data/0/id").asText()).isEqualTo(ready.toString());
        JsonNode page2 = get("/api/v1/documents?limit=4&cursor=" + page1.at("/page/cursor").asText(), owner).getBody();
        assertThat(page2.path("data")).hasSize(2);
        assertThat(page2.at("/page/hasMore").asBoolean()).isFalse();

        assertThat(get("/api/v1/documents?status=READY", owner).getBody().path("data")).hasSize(1);
        assertThat(get("/api/v1/documents?q=DOC3", owner).getBody().path("data")).hasSize(1);
        assertThat(get("/api/v1/documents?status=NOPE", owner).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }
}
