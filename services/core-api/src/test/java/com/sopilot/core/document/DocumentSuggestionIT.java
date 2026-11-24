package com.sopilot.core.document;

import com.fasterxml.jackson.databind.JsonNode;
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

/** V2-25: ai-service suggestions reach the document only where the user has not set the field. */
class DocumentSuggestionIT extends ApiIT {

    private static final String TOKEN = "test-internal-token";

    private ResponseEntity<JsonNode> internal(HttpMethod method, String path, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", TOKEN);
        return http.exchange(path, method, new HttpEntity<>(body, headers), JsonNode.class);
    }

    /** Uploads a document and marks its only version READY; returns (document id, version id). */
    private UUID[] readyDocument(Actor owner, String filename, String... tags) {
        var params = new org.springframework.util.LinkedMultiValueMap<String, String>();
        for (String t : tags) {
            params.add("tags", t);
        }
        // Distinct bytes per file name: identical content is deduplicated by SHA-256.
        byte[] sop = ("# Quy trình mua hàng\n\nNội dung của " + filename + ".\n").getBytes(StandardCharsets.UTF_8);
        UUID doc = id(upload("/api/v1/documents", owner, filename, sop, params), "id");
        UUID version = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT id FROM core.document_versions WHERE document_id = ?", UUID.class, doc));
        internal(HttpMethod.PATCH, "/internal/documents/" + doc + "/versions/" + version + "/status",
                Map.of("workspaceId", owner.workspaceId().toString(), "status", "READY", "attempt", 0,
                        "pageCount", 1, "detectedLanguage", "vi", "chunkCount", 1,
                        "extracted", Map.of("docCode", "QT-MH-01", "revisionLabel", "01", "effectiveDate", "2026-01-15")));
        return new UUID[] {doc, version};
    }

    private Map<String, Object> suggestion(Actor owner, UUID version, Map<String, Object> overrides) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("workspaceId", owner.workspaceId().toString());
        body.put("versionId", version.toString());
        body.put("method", "LLM");
        body.put("title", "Quy trình mua hàng");
        body.put("description", "Quy trình đặt mua hàng nội bộ.");
        body.put("categoryId", null);
        body.put("proposedCategoryName", null);
        body.put("tags", List.of());
        body.putAll(overrides);
        return body;
    }

    private JsonNode document(Actor owner, UUID doc) {
        return get("/api/v1/documents/" + doc, owner).getBody().path("data");
    }

    @Test
    void ingestRequestCarriesTheWorkspaceCategoriesAndTagNames() throws Exception {
        Actor owner = newTeamWorkspace("sgp");
        UUID cat = id(post("/api/v1/categories", owner, Map.of("name", "Mua sắm")), "id");
        UUID[] doc = readyDocument(owner, "p.md", "quy trình");
        String payload = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT payload::text FROM core.outbox_events WHERE aggregate_id = ? AND event_type = 'INGEST_REQUESTED'",
                String.class, doc[0]));
        JsonNode suggest = json.readTree(payload).path("suggest");
        assertThat(suggest.path("enabled").asBoolean()).isTrue();
        assertThat(suggest.path("categories").get(0).path("id").asText()).isEqualTo(cat.toString());
        assertThat(suggest.path("tags").toString()).contains("quy trình");
    }

    @Test
    void suggestionFillsFieldsTheUserHasNotSet() {
        Actor owner = newTeamWorkspace("sga");
        UUID cat = id(post("/api/v1/categories", owner, Map.of("name", "Mua sắm")), "id");
        readyDocument(owner, "other.md", "quy trình"); // makes the tag exist; the user sets it on no document
        UUID[] doc = readyDocument(owner, "p.md");

        ResponseEntity<JsonNode> r = internal(HttpMethod.PUT, "/internal/documents/" + doc[0] + "/suggestions",
                suggestion(owner, doc[1], Map.of("categoryId", cat.toString(), "tags", List.of("quy trình", "không có"))));
        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(r.getBody().path("applied").asBoolean()).isTrue();

        JsonNode d = document(owner, doc[0]);
        assertThat(d.path("title").asText()).isEqualTo("p"); // the suggested title is stored, not applied
        assertThat(d.path("fieldSources").path("title").asText()).isEqualTo("SYSTEM");
        assertThat(d.path("suggestions").path("title").asText()).isEqualTo("Quy trình mua hàng");
        assertThat(d.path("description").asText()).isEqualTo("Quy trình đặt mua hàng nội bộ.");
        assertThat(d.path("category").path("id").asText()).isEqualTo(cat.toString());
        assertThat(d.path("tags").toString()).contains("quy trình").doesNotContain("không có");
    }

    @Test
    void userSetFieldsAreNeverOverwritten() {
        Actor owner = newTeamWorkspace("sgu");
        UUID cat = id(post("/api/v1/categories", owner, Map.of("name", "Mua sắm")), "id");
        UUID[] doc = readyDocument(owner, "p.md");
        call(HttpMethod.PATCH, "/api/v1/documents/" + doc[0], owner, Map.of("description", "Mô tả của người dùng"));

        internal(HttpMethod.PUT, "/internal/documents/" + doc[0] + "/suggestions",
                suggestion(owner, doc[1], Map.of("categoryId", cat.toString())));

        JsonNode d = document(owner, doc[0]);
        assertThat(d.path("description").asText()).isEqualTo("Mô tả của người dùng");
        assertThat(d.path("category").path("id").asText()).isEqualTo(cat.toString()); // not user-set
    }

    @Test
    void aTitleTheUserSetIsNotSuggestedAgainAndANewCategoryNameIsOffered() {
        Actor owner = newTeamWorkspace("sgt");
        UUID[] doc = readyDocument(owner, "p.md");
        internal(HttpMethod.PUT, "/internal/documents/" + doc[0] + "/suggestions",
                suggestion(owner, doc[1], Map.of("proposedCategoryName", "Mua sắm")));

        JsonNode before = document(owner, doc[0]);
        assertThat(before.path("suggestions").path("title").asText()).isEqualTo("Quy trình mua hàng");
        assertThat(before.path("suggestions").path("proposedCategoryName").asText()).isEqualTo("Mua sắm");

        call(HttpMethod.PATCH, "/api/v1/documents/" + doc[0], owner, Map.of("title", "Tên do người dùng"));

        JsonNode after = document(owner, doc[0]);
        assertThat(after.path("title").asText()).isEqualTo("Tên do người dùng");
        assertThat(after.path("suggestions").path("title").isMissingNode()
                || after.path("suggestions").path("title").isNull()).isTrue();
        assertThat(after.path("suggestions").path("proposedCategoryName").asText()).isEqualTo("Mua sắm");
    }

    @Test
    void suggestionForAVersionThatIsNotCurrentChangesNothing() {
        Actor owner = newTeamWorkspace("sgs");
        UUID[] doc = readyDocument(owner, "p.md");
        JsonNode before = document(owner, doc[0]);
        ResponseEntity<JsonNode> r = internal(HttpMethod.PUT, "/internal/documents/" + doc[0] + "/suggestions",
                suggestion(owner, UUID.randomUUID(), Map.of()));
        assertThat(r.getBody().path("applied").asBoolean()).isFalse();
        assertThat(document(owner, doc[0]).path("description")).isEqualTo(before.path("description"));
    }

    @Test
    void categoryFromAnotherWorkspaceIsIgnored() {
        Actor owner = newTeamWorkspace("sgx");
        Actor other = newTeamWorkspace("sgy");
        UUID foreignCat = id(post("/api/v1/categories", other, Map.of("name", "Khác")), "id");
        UUID[] doc = readyDocument(owner, "p.md");
        internal(HttpMethod.PUT, "/internal/documents/" + doc[0] + "/suggestions",
                suggestion(owner, doc[1], Map.of("categoryId", foreignCat.toString())));
        assertThat(document(owner, doc[0]).path("category").isNull()).isTrue();
    }

    @Test
    void callbackFromAnotherWorkspaceIsNotFound() {
        Actor owner = newTeamWorkspace("sgo");
        Actor intruder = newTeamWorkspace("sgi");
        UUID[] doc = readyDocument(owner, "p.md");
        ResponseEntity<JsonNode> r = internal(HttpMethod.PUT, "/internal/documents/" + doc[0] + "/suggestions",
                suggestion(intruder, doc[1], Map.of()));
        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void versionOfAnotherDocumentIsRejectedAndWritesNothing() {
        Actor owner = newTeamWorkspace("sgf");
        UUID[] mine = readyDocument(owner, "mine.md");
        UUID[] theirs = readyDocument(owner, "theirs.md");
        long before = countSuggestions(owner, theirs[1]);

        ResponseEntity<JsonNode> r = internal(HttpMethod.PUT, "/internal/documents/" + mine[0] + "/suggestions",
                suggestion(owner, theirs[1], Map.of("description", "Ghi đè từ tài liệu khác")));

        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(countSuggestions(owner, theirs[1])).isEqualTo(before);
        assertThat(asTenant(owner, () -> jdbc.queryForObject(
                "SELECT count(*) FROM core.document_suggestions WHERE document_id = ?", Long.class, mine[0])))
                .isZero();
    }

    @Test
    void callbackWithoutTheInternalTokenIsUnauthorizedAndWritesNothing() {
        Actor owner = newTeamWorkspace("sgt");
        UUID[] doc = readyDocument(owner, "p.md");
        long before = countSuggestions(owner, doc[1]);
        Map<String, Object> body = suggestion(owner, doc[1], Map.of("description", "Không được ghi"));

        HttpHeaders wrong = new HttpHeaders();
        wrong.setContentType(MediaType.APPLICATION_JSON);
        wrong.set("X-Internal-Token", "wrong-token");
        ResponseEntity<JsonNode> badToken = http.exchange("/internal/documents/" + doc[0] + "/suggestions",
                HttpMethod.PUT, new HttpEntity<>(body, wrong), JsonNode.class);

        HttpHeaders none = new HttpHeaders();
        none.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<JsonNode> missing = http.exchange("/internal/documents/" + doc[0] + "/suggestions",
                HttpMethod.PUT, new HttpEntity<>(body, none), JsonNode.class);

        assertThat(badToken.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(missing.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(countSuggestions(owner, doc[1])).isEqualTo(before);
        JsonNode description = document(owner, doc[0]).path("description");
        assertThat(description.isNull() || description.isMissingNode()).isTrue();
    }

    private long countSuggestions(Actor owner, UUID version) {
        return asTenant(owner, () -> jdbc.queryForObject(
                "SELECT count(*) FROM core.document_suggestions WHERE version_id = ?", Long.class, version));
    }

    @Test
    void unknownMethodIsRejected() {
        Actor owner = newTeamWorkspace("sgm");
        UUID[] doc = readyDocument(owner, "p.md");
        ResponseEntity<JsonNode> r = internal(HttpMethod.PUT, "/internal/documents/" + doc[0] + "/suggestions",
                suggestion(owner, doc[1], Map.of("method", "GUESS")));
        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }
}
