package com.sopilot.core.tenancy;

import com.fasterxml.jackson.databind.JsonNode;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.TestPropertySource;

import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * FR-19 through the HTTP API (V2-14): three workspaces, each with a "secret" in every kind of data the
 * API can return. No endpoint, called with any workspace's token, may return another workspace's secret, and
 * every attempt to reach another workspace's object by id is a 404. The pool has a single connection, so every
 * request below reuses the same physical connection: a tenant must not survive from one request to the next.
 * Database-level checks of every table and both roles are in {@code tests/tenant-isolation}.
 */
@TestPropertySource(properties = "spring.datasource.hikari.maximum-pool-size=1")
class TenantIsolationApiIT extends ApiIT {

    private record World(Actor admin, Actor member, String key, UUID document, UUID version, UUID department,
                         Map<String, String> secrets) {
    }

    private List<World> worlds;

    @BeforeEach
    void threeWorkspaces() {
        worlds = new ArrayList<>();
        for (String key : List.of("A", "B", "C")) {
            Actor owner = newTeamWorkspace("own" + key.toLowerCase());
            Actor member = addMember(owner.workspaceId(), "MEMBER", "mem" + key.toLowerCase());
            String doc = "SECRET" + key + "document" + UUID.randomUUID().toString().substring(0, 8);
            String dept = "SECRET" + key + "department" + UUID.randomUUID().toString().substring(0, 8);
            String name = "SECRET" + key + "person" + UUID.randomUUID().toString().substring(0, 8);
            ResponseEntity<JsonNode> created = uploadDocument(owner, doc + ".md", markdown(doc));
            UUID document = id(created, "id");
            UUID version = id(created, "latestVersion", "id");
            UUID department = id(post("/api/v1/departments", owner, Map.of("name", dept)), "id");
            patch("/api/v1/members/" + member.userId(), owner, Map.of("displayName", name,
                    "departmentId", department.toString()));
            patch("/api/v1/documents/" + document, owner, Map.of("description", "SECRET" + key + "description"));
            worlds.add(new World(owner, member, key, document, version, department,
                    Map.of("document", doc, "department", dept, "person", name,
                            "description", "SECRET" + key + "description")));
        }
    }

    private List<String> getEndpoints(World own, World other) {
        return List.of("/api/v1/documents", "/api/v1/documents?q=SECRET", "/api/v1/documents?status=UPLOADED",
                "/api/v1/departments?includeArchived=true", "/api/v1/members", "/api/v1/members?q=SECRET",
                "/api/v1/members/me", "/api/v1/audit-logs", "/api/v1/audit-logs?limit=100",
                "/api/v1/documents/" + own.document(), "/api/v1/documents/" + own.document() + "/versions",
                "/api/v1/documents/" + own.document() + "/download-url");
    }

    private void assertNoSecretsOf(String body, World viewer, String via) {
        for (World other : worlds) {
            if (other == viewer) {
                continue;
            }
            assertThat(body).as("%s as workspace %s leaked a secret of %s", via, viewer.key(), other.key())
                    .doesNotContain("SECRET" + other.key());
        }
    }

    @Test
    void noEndpointReturnsAnotherWorkspacesSecretWhoeverAsks() {
        for (int round = 0; round < 2; round++) {
            for (World viewer : worlds) {
                for (Actor caller : List.of(viewer.admin(), viewer.member())) {
                    for (String path : getEndpoints(viewer, viewer)) {
                        ResponseEntity<JsonNode> r = get(path, caller);
                        assertNoSecretsOf(String.valueOf(r.getBody()), viewer, path);
                    }
                }
            }
        }
    }

    @Test
    void theOwnerCanReadItsOwnSecretsSoTheCheckAboveIsNotVacuous() {
        for (World w : worlds) {
            String documents = String.valueOf(get("/api/v1/documents", w.admin()).getBody());
            assertThat(documents).contains(w.secrets().get("document")).contains(w.secrets().get("description"));
            assertThat(String.valueOf(get("/api/v1/departments", w.admin()).getBody()))
                    .contains(w.secrets().get("department"));
            assertThat(String.valueOf(get("/api/v1/members", w.admin()).getBody())).contains(w.secrets().get("person"));
            assertThat(String.valueOf(get("/api/v1/audit-logs", w.admin()).getBody())).contains("DOCUMENT_UPLOADED");
            assertThat(String.valueOf(get("/api/v1/documents", w.member()).getBody()))
                    .contains(w.secrets().get("document"));
        }
    }

    @Test
    void listsContainExactlyTheCallersOwnRows() {
        for (World w : worlds) {
            assertThat(get("/api/v1/documents", w.admin()).getBody().path("data")).hasSize(1);
            assertThat(get("/api/v1/departments?includeArchived=true", w.admin()).getBody().path("data")).hasSize(1);
            assertThat(get("/api/v1/members", w.admin()).getBody().path("data")).hasSize(2);
            for (JsonNode entry : get("/api/v1/audit-logs?limit=100", w.admin()).getBody().path("data")) {
                assertThat(entry.path("actorId").asText()).isIn(w.admin().userId().toString(),
                        w.member().userId().toString());
            }
        }
    }

    @Test
    void reachingAnotherWorkspacesObjectByIdIsAlwaysNotFound() {
        World a = worlds.get(0);
        World b = worlds.get(1);
        UUID bDoc = b.document();

        List<ResponseEntity<JsonNode>> attempts = List.of(
                get("/api/v1/documents/" + bDoc, a.admin()),
                get("/api/v1/documents/" + bDoc + "/versions", a.admin()),
                get("/api/v1/documents/" + bDoc + "/download-url", a.admin()),
                patch("/api/v1/documents/" + bDoc, a.admin(), Map.of("title", "pwned")),
                post("/api/v1/documents/" + bDoc + "/retry", a.admin(), null),
                delete("/api/v1/documents/" + bDoc, a.admin()),
                upload("/api/v1/documents/" + bDoc + "/versions", a.admin(), "x.md", markdown("x")),
                patch("/api/v1/members/" + b.member().userId(), a.admin(), Map.of("jobTitle", "pwned")),
                post("/api/v1/members/" + b.member().userId() + "/suspend", a.admin(), null),
                delete("/api/v1/members/" + b.member().userId(), a.admin()),
                patch("/api/v1/departments/" + b.department(), a.admin(), Map.of("name", "pwned")),
                delete("/api/v1/departments/" + b.department(), a.admin()),
                patch("/api/v1/members/" + b.admin().userId(), a.admin(), Map.of("departmentId", b.department().toString())));
        for (ResponseEntity<JsonNode> r : attempts) {
            assertThat(r.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        }
        // A department of another workspace cannot be assigned to one's own member either.
        assertThat(patch("/api/v1/members/" + a.member().userId(), a.admin(),
                Map.of("departmentId", b.department().toString())).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);

        // B's data is exactly as it was.
        JsonNode doc = get("/api/v1/documents/" + bDoc, b.admin()).getBody().path("data");
        assertThat(doc.path("title").asText()).isEqualTo(b.secrets().get("document"));
        assertThat(doc.at("/latestVersion/status").asText()).isEqualTo("UPLOADED");
        assertThat(get("/api/v1/members", b.admin()).getBody().path("data")).hasSize(2);
        assertThat(get("/api/v1/departments", b.admin()).getBody().path("data")).hasSize(1);
    }

    @Test
    void forgedMissingAndExpiredTokensNeverReachData() throws Exception {
        World a = worlds.get(0);
        World b = worlds.get(1);
        RSAKey attacker = new RSAKeyGenerator(2048).keyID("attacker").generate();

        // Right workspace id, signed by someone else.
        Actor forged = new Actor(a.admin().userId(), b.admin().workspaceId(), a.admin().role(),
                sign(attacker, b.admin().workspaceId(), "OWNER", 600));
        assertThat(get("/api/v1/documents", forged).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        // Genuine token with its payload edited to another workspace: the signature no longer matches.
        String[] parts = a.admin().token().split("\\.");
        String payload = new String(java.util.Base64.getUrlDecoder().decode(parts[1]));
        String swapped = payload.replace(a.admin().workspaceId().toString(), b.admin().workspaceId().toString());
        assertThat(swapped).isNotEqualTo(payload);
        Actor edited = new Actor(a.admin().userId(), b.admin().workspaceId(), a.admin().role(), parts[0] + "."
                + java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(swapped.getBytes()) + "." + parts[2]);
        assertThat(get("/api/v1/documents", edited).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        // Missing, empty, expired.
        assertThat(get("/api/v1/documents", null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(get("/api/v1/documents", new Actor(a.admin().userId(), a.admin().workspaceId(), a.admin().role(), ""))
                .getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(get("/api/v1/documents", new Actor(a.admin().userId(), a.admin().workspaceId(), a.admin().role(),
                signExpired(a))).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        for (String path : List.of("/api/v1/members", "/api/v1/departments", "/api/v1/audit-logs")) {
            assertThat(call(HttpMethod.GET, path, null, null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        }
    }

    private String sign(RSAKey key, UUID workspace, String role, long ttlSeconds) throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder().issuer("sopilot-core").audience(List.of("sopilot-core"))
                .subject(UUID.randomUUID().toString()).claim("wid", workspace.toString()).claim("wrole", role)
                .expirationTime(new Date(System.currentTimeMillis() + ttlSeconds * 1000)).build();
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.getKeyID())
                .type(JOSEObjectType.JWT).build(), claims);
        jwt.sign(new RSASSASigner(key));
        return jwt.serialize();
    }

    private String signExpired(World w) throws Exception {
        // Signed by a throwaway key as well: expiry is checked after the signature, so this is doubly rejected.
        return sign(new RSAKeyGenerator(2048).keyID("x").generate(), w.admin().workspaceId(), "OWNER", -3600);
    }

    @Test
    void aMemberTokenNeverGainsAnotherWorkspacesPrivileges() {
        World a = worlds.get(0);
        World b = worlds.get(1);

        // A's member is a plain MEMBER everywhere; being an OWNER of B (as a different user) changes nothing for A.
        assertThat(post("/api/v1/departments", a.member(), Map.of("name", "x")).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(get("/api/v1/audit-logs", a.member()).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(get("/api/v1/documents/" + b.document(), a.member()).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void internalCallbacksCannotCrossWorkspacesEvenWithTheInternalToken() {
        World a = worlds.get(0);
        World b = worlds.get(1);
        org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
        headers.set("X-Internal-Token", "test-internal-token");
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);

        // The body says workspace A, the version belongs to B: the row is invisible under A's tenant context.
        ResponseEntity<JsonNode> r = http.exchange("/internal/documents/" + b.document() + "/versions/" + b.version()
                        + "/status", HttpMethod.PATCH, new org.springframework.http.HttpEntity<>(
                        Map.of("workspaceId", a.admin().workspaceId().toString(), "status", "PROCESSING", "attempt", 0),
                        headers), JsonNode.class);

        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(asTenant(b.admin(), () -> jdbc.queryForObject("SELECT status FROM core.document_versions WHERE id = ?",
                String.class, b.version()))).isEqualTo("UPLOADED");
    }

    @Test
    void theApplicationFilterAloneStillHoldsIfRlsIsSwitchedOffOnDocuments() {
        // Two layers (ADR-005): every query also filters workspace_id. Switch the first layer off to prove it.
        World a = worlds.get(0);
        World b = worlds.get(1);
        migrator("ALTER TABLE core.documents DISABLE ROW LEVEL SECURITY");
        migrator("ALTER TABLE core.document_versions DISABLE ROW LEVEL SECURITY");
        try {
            assertThat(get("/api/v1/documents/" + b.document(), a.admin()).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
            assertThat(String.valueOf(get("/api/v1/documents", a.admin()).getBody())).doesNotContain("SECRETB");
            assertThat(get("/api/v1/documents/" + b.document() + "/versions", a.admin()).getStatusCode())
                    .isEqualTo(HttpStatus.NOT_FOUND);
            assertThat(delete("/api/v1/documents/" + b.document(), a.admin()).getStatusCode())
                    .isEqualTo(HttpStatus.NOT_FOUND);
        } finally {
            migrator("ALTER TABLE core.documents ENABLE ROW LEVEL SECURITY");
            migrator("ALTER TABLE core.document_versions ENABLE ROW LEVEL SECURITY");
        }
        // And the database layer is back: no context, no rows.
        assertThat(tenant.run(null, null, () -> jdbc.queryForObject("SELECT count(*) FROM core.documents", Long.class)))
                .isZero();
    }
}
