package com.sopilot.core.identity;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.crypto.RSASSAVerifier;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jwt.SignedJWT;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.support.V2Postgres;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * JIT against real Postgres with the production roles and migrations (V2-11 §4 Integration):
 * idempotent and concurrent first login, OWNER membership of the PERSONAL workspace, and the
 * access token verified through the published JWKS.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class IdentityJitIT {

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        V2Postgres.register(registry);
    }

    @Autowired
    TestRestTemplate http;
    @Autowired
    IdentityService identityService;
    @Autowired
    ObjectMapper json;

    @Test
    void devLoginCreatesUserPersonalWorkspaceAndOwnerMembershipOnce() throws Exception {
        String email = "an-" + UUID.randomUUID() + "@acme.com";

        JsonNode first = devLogin(email, "An");
        JsonNode second = devLogin(email.toUpperCase(), "An again");

        assertThat(second.at("/user/id").asText()).isEqualTo(first.at("/user/id").asText());
        assertThat(second.at("/workspace/id").asText()).isEqualTo(first.at("/workspace/id").asText());
        assertThat(first.at("/workspace/kind").asText()).isEqualTo("PERSONAL");
        assertThat(first.at("/workspace/role").asText()).isEqualTo("OWNER");
        assertThat(first.at("/workspace/name").asText()).isEqualTo("An's workspace");
        assertThat(first.at("/expiresIn").asLong()).isEqualTo(900);

        UUID userId = UUID.fromString(first.at("/user/id").asText());
        try (Connection admin = superuser()) {
            assertThat(count(admin, "core.users WHERE id = '" + userId + "'")).isEqualTo(1);
            assertThat(count(admin, "core.external_identities WHERE user_id = '" + userId + "' AND issuer = 'sopilot-dev'")).isEqualTo(1);
            assertThat(count(admin, "core.workspaces WHERE created_by = '" + userId + "' AND kind = 'PERSONAL'")).isEqualTo(1);
            assertThat(count(admin, "core.memberships WHERE user_id = '" + userId
                    + "' AND role = 'OWNER' AND status = 'ACTIVE' AND email = '" + email + "'")).isEqualTo(1);
            assertThat(scalar(admin, "SELECT last_active_workspace_id::text FROM core.users WHERE id = '" + userId + "'"))
                    .isEqualTo(first.at("/workspace/id").asText());
        }
    }

    @Test
    void concurrentFirstLoginsProvisionExactlyOnce() throws Exception {
        String subject = "google-sub-" + UUID.randomUUID();
        var claims = new ExternalIdentityClaims(GoogleIdTokenVerifier.CANONICAL_ISSUER, subject,
                subject + "@gmail.com", "Concurrent", null, null);
        int threads = 8;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        List<Future<LoginResponse>> results = new ArrayList<>();
        try {
            for (int i = 0; i < threads; i++) {
                Callable<LoginResponse> call = () -> {
                    start.await();
                    return identityService.login(claims);
                };
                results.add(pool.submit(call));
            }
            start.countDown();
            Set<UUID> users = new HashSet<>();
            Set<UUID> workspaces = new HashSet<>();
            for (Future<LoginResponse> f : results) {
                LoginResponse r = f.get();
                users.add(r.user().id());
                workspaces.add(r.workspace().id());
            }
            assertThat(users).hasSize(1);
            assertThat(workspaces).hasSize(1);
        } finally {
            pool.shutdownNow();
        }

        try (Connection admin = superuser()) {
            assertThat(count(admin, "core.external_identities WHERE subject = '" + subject + "'")).isEqualTo(1);
            assertThat(count(admin, "core.users WHERE email = '" + subject + "@gmail.com'")).isEqualTo(1);
            assertThat(count(admin, "core.workspaces w JOIN core.external_identities e ON e.user_id = w.created_by "
                    + "WHERE e.subject = '" + subject + "'")).isEqualTo(1);
            assertThat(count(admin, "core.memberships m JOIN core.external_identities e ON e.user_id = m.user_id "
                    + "WHERE e.subject = '" + subject + "'")).isEqualTo(1);
        }
    }

    @Test
    void sameEmailFromDifferentIssuersIsTwoUsers() {
        String email = "shared-" + UUID.randomUUID() + "@gmail.com";
        LoginResponse google = identityService.login(new ExternalIdentityClaims(
                GoogleIdTokenVerifier.CANONICAL_ISSUER, "sub-" + UUID.randomUUID(), email, "G", null, "gmail.com"));
        LoginResponse dev = identityService.login(new ExternalIdentityClaims(
                DevLoginController.DEV_ISSUER, email, email, "D", null, null));

        assertThat(google.user().id()).isNotEqualTo(dev.user().id());
        assertThat(google.workspace().id()).isNotEqualTo(dev.workspace().id());
    }

    @Test
    void accessTokenVerifiesAgainstPublishedJwks() throws Exception {
        JsonNode login = devLogin("jwks-" + UUID.randomUUID() + "@acme.com", null);

        ResponseEntity<String> jwks = http.getForEntity("/.well-known/jwks.json", String.class);
        assertThat(jwks.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(jwks.getBody()).doesNotContain("\"d\"");

        SignedJWT token = SignedJWT.parse(login.at("/accessToken").asText());
        RSAKey key = JWKSet.parse(jwks.getBody()).getKeyByKeyId(token.getHeader().getKeyID()).toRSAKey();
        assertThat(token.verify(new RSASSAVerifier(key))).isTrue();

        var claims = token.getJWTClaimsSet();
        assertThat(claims.getSubject()).isEqualTo(login.at("/user/id").asText());
        assertThat(claims.getStringClaim("wid")).isEqualTo(login.at("/workspace/id").asText());
        assertThat(claims.getStringClaim("wrole")).isEqualTo("OWNER");
        assertThat(claims.getClaims()).containsKey("wdept");
        long ttl = claims.getExpirationTime().toInstant().getEpochSecond() - claims.getIssueTime().toInstant().getEpochSecond();
        assertThat(ttl).isLessThanOrEqualTo(900);
    }

    @Test
    void googleLoginWithoutNonceCookieIsRejectedGenerically() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<String> response = http.postForEntity("/api/v1/auth/google",
                new HttpEntity<>("{\"idToken\":\"eyJhbGciOiJSUzI1NiJ9.e30.c2ln\"}", headers), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(response.getBody()).contains("INVALID_GOOGLE_TOKEN").doesNotContain("NOT_CONFIGURED", "NONCE");
    }

    private JsonNode devLogin(String email, String displayName) throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String body = displayName == null
                ? json.writeValueAsString(java.util.Map.of("email", email))
                : json.writeValueAsString(java.util.Map.of("email", email, "displayName", displayName));
        ResponseEntity<String> response = http.postForEntity("/api/v1/auth/dev-login",
                new HttpEntity<>(body, headers), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getHeaders().getFirst("X-Trace-Id")).isNotBlank();
        return json.readTree(response.getBody()).get("data");
    }

    static Connection superuser() throws Exception {
        var pg = V2Postgres.container();
        return DriverManager.getConnection(pg.getJdbcUrl(), pg.getUsername(), pg.getPassword());
    }

    static long count(Connection c, String fromWhere) throws Exception {
        return Long.parseLong(scalar(c, "SELECT count(*) FROM " + fromWhere));
    }

    static String scalar(Connection c, String sql) throws Exception {
        try (Statement st = c.createStatement(); ResultSet rs = st.executeQuery(sql)) {
            rs.next();
            return rs.getString(1);
        }
    }
}
