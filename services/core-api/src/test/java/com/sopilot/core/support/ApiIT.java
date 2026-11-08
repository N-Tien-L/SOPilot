package com.sopilot.core.support;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.identity.ExternalIdentityClaims;
import com.sopilot.core.identity.IdentityService;
import com.sopilot.core.identity.SessionTokenService;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.outbox.OutboxDispatcher;
import com.sopilot.core.security.AccessTokenVerifier;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tenancy.TenantTx;
import com.sopilot.core.security.WorkspaceRole;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.context.annotation.Import;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.UUID;
import java.util.function.Supplier;

/**
 * Base for API-level integration tests: real Postgres (production roles and RLS), S3 and ai-service
 * replaced by in-process fakes. Workspaces beyond the personal one and extra members are seeded as
 * {@code sopilot_migrator}, because team-workspace creation and invitations belong to V2-29/V2-30.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
@Import(TestBeans.class)
public abstract class ApiIT {

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        V2Postgres.register(registry);
    }

    @Autowired protected TestRestTemplate http;
    @Autowired protected IdentityService identity;
    @Autowired protected SessionTokenService sessions;
    @Autowired protected TenantTx tenant;
    @Autowired protected JdbcTemplate jdbc;
    @Autowired protected ObjectMapper json;
    @Autowired protected InMemoryStorage storage;
    @Autowired protected RecordingAiClient ai;
    @Autowired protected OutboxDispatcher dispatcher;
    @Autowired protected AccessTokenVerifier verifier;

    @BeforeEach
    void resetFakes() {
        storage.clear();
        ai.reset();
    }

    /** A signed-in caller bound to one workspace. */
    public record Actor(UUID userId, UUID workspaceId, WorkspaceRole role, String token) {
        public AuthPrincipal principal() {
            return new AuthPrincipal(userId, workspaceId, role, null);
        }
    }

    // ---- people and workspaces --------------------------------------------------------------------

    protected static String email(String prefix) {
        return prefix + "-" + UUID.randomUUID() + "@acme.com";
    }

    /** First login: user, PERSONAL workspace and OWNER membership. */
    protected Actor loginPersonal(String prefix) {
        LoginResponse login = identity.login(new ExternalIdentityClaims("sopilot-dev", email(prefix), email(prefix),
                prefix, null, null));
        return new Actor(login.user().id(), login.workspace().id(), WorkspaceRole.OWNER, login.accessToken());
    }

    /** A TEAM workspace owned by a fresh user, seeded directly (V2-29 adds the API). */
    protected Actor newTeamWorkspace(String prefix) {
        UUID userId = seedUser(email(prefix), prefix);
        UUID workspaceId = UUID.randomUUID();
        migrator("INSERT INTO core.workspaces (id, name, kind, created_by) VALUES (?, ?, 'TEAM', ?)",
                workspaceId, prefix + " team", userId);
        seedMembership(workspaceId, userId, "OWNER");
        return actorFor(userId, workspaceId);
    }

    /** A new user with the given role in an existing workspace. */
    protected Actor addMember(UUID workspaceId, String role, String prefix) {
        UUID userId = seedUser(email(prefix), prefix);
        seedMembership(workspaceId, userId, role);
        return actorFor(userId, workspaceId);
    }

    /** Token for the membership as it is now (this exercises {@code SessionTokenService}). */
    protected Actor actorFor(UUID userId, UUID workspaceId) {
        String token = sessions.reissue(userId, workspaceId).value();
        AuthPrincipal p = verifier.verify(token).orElseThrow();
        return new Actor(userId, workspaceId, p.role(), token);
    }

    protected UUID seedUser(String email, String displayName) {
        UUID id = UUID.randomUUID();
        migrator("INSERT INTO core.users (id, email, display_name) VALUES (?, ?, ?)", id, email, displayName);
        return id;
    }

    protected void seedMembership(UUID workspaceId, UUID userId, String role) {
        migrator("INSERT INTO core.memberships (workspace_id, user_id, role, email, display_name) "
                + "SELECT ?, u.id, ?, u.email, u.display_name FROM core.users u WHERE u.id = ?",
                workspaceId, role, userId);
    }

    /** Runs SQL as the schema owner (bypasses nothing it does not own; RLS-forced tables are not touched here). */
    protected static void migrator(String sql, Object... args) {
        try (Connection c = DriverManager.getConnection(V2Postgres.container().getJdbcUrl(), "sopilot_migrator",
                V2Postgres.MIGRATOR_PASSWORD); PreparedStatement ps = c.prepareStatement(sql)) {
            for (int i = 0; i < args.length; i++) {
                ps.setObject(i + 1, args[i]);
            }
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new IllegalStateException("Seed statement failed: " + e.getMessage(), e);
        }
    }

    /** Reads or writes tenant tables as the application role, inside the actor's RLS context. */
    protected <T> T asTenant(Actor actor, Supplier<T> body) {
        return tenant.run(actor.workspaceId(), actor.userId(), body);
    }

    // ---- HTTP -----------------------------------------------------------------------------------

    protected ResponseEntity<JsonNode> call(HttpMethod method, String path, Actor actor, Object body) {
        HttpHeaders headers = new HttpHeaders();
        if (actor != null) {
            headers.setBearerAuth(actor.token());
        }
        if (body != null) {
            headers.setContentType(MediaType.APPLICATION_JSON);
        }
        return http.exchange(path, method, new HttpEntity<>(body, headers), JsonNode.class);
    }

    protected ResponseEntity<JsonNode> get(String path, Actor actor) {
        return call(HttpMethod.GET, path, actor, null);
    }

    protected ResponseEntity<JsonNode> post(String path, Actor actor, Object body) {
        return call(HttpMethod.POST, path, actor, body);
    }

    protected ResponseEntity<JsonNode> patch(String path, Actor actor, Object body) {
        return call(HttpMethod.PATCH, path, actor, body);
    }

    protected ResponseEntity<JsonNode> delete(String path, Actor actor) {
        return call(HttpMethod.DELETE, path, actor, null);
    }

    protected ResponseEntity<JsonNode> upload(String path, Actor actor, String filename, byte[] content) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(actor.token());
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(content) {
            @Override
            public String getFilename() {
                return filename;
            }
        });
        return http.exchange(path, HttpMethod.POST, new HttpEntity<>(form, headers), JsonNode.class);
    }

    protected ResponseEntity<JsonNode> uploadDocument(Actor actor, String filename, byte[] content) {
        return upload("/api/v1/documents", actor, filename, content);
    }

    /** Distinct Markdown content, so each call yields a different SHA-256. */
    protected static byte[] markdown(String text) {
        return ("# " + text + "\n\nBody of " + text + " " + UUID.randomUUID() + "\n").getBytes(StandardCharsets.UTF_8);
    }

    protected static byte[] pdf(String text) {
        return ("%PDF-1.7\n% " + text + " " + UUID.randomUUID() + "\n%%EOF\n").getBytes(StandardCharsets.US_ASCII);
    }

    protected UUID id(ResponseEntity<JsonNode> response, String... path) {
        JsonNode node = response.getBody().path("data");
        for (String p : path) {
            node = node.path(p);
        }
        return UUID.fromString(node.asText());
    }
}
