package com.sopilot.core.tenancy;

import com.sopilot.core.identity.ExternalIdentityClaims;
import com.sopilot.core.identity.IdentityService;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.support.V2Postgres;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Schema isolation and RLS as {@code sopilot_core_app} (V2-11 §4; TECH §4, §10). The pool has
 * one connection, so every transaction below reuses the same physical connection: a tenant
 * bound in one transaction must not be visible in the next.
 */
@SpringBootTest
@ActiveProfiles("test")
class TenantIsolationIT {

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        V2Postgres.register(registry);
        registry.add("spring.datasource.hikari.maximum-pool-size", () -> 1);
    }

    @Autowired
    IdentityService identityService;
    @Autowired
    JdbcTemplate jdbc;
    @Autowired
    TransactionTemplate tx;
    @Autowired
    RlsContext rls;

    private LoginResponse alice;
    private LoginResponse bob;

    @BeforeEach
    void twoUsers() {
        alice = identityService.login(dev("alice-" + UUID.randomUUID() + "@acme.com"));
        bob = identityService.login(dev("bob-" + UUID.randomUUID() + "@acme.com"));
    }

    @Test
    void withoutTenantContextNoWorkspaceRowsAreVisible() {
        Long workspaces = tx.execute(s -> jdbc.queryForObject("SELECT count(*) FROM core.workspaces", Long.class));
        Long memberships = tx.execute(s -> jdbc.queryForObject("SELECT count(*) FROM core.memberships", Long.class));

        assertThat(workspaces).isZero();
        assertThat(memberships).isZero();
    }

    @Test
    void userContextSeesOnlyOwnWorkspaces() {
        List<UUID> visible = tx.execute(s -> {
            rls.bind(null, alice.user().id());
            return jdbc.queryForList("SELECT id FROM core.workspaces", UUID.class);
        });

        assertThat(visible).containsExactly(alice.workspace().id());
    }

    @Test
    void workspaceContextCannotReadOrWriteAnotherWorkspace() {
        Long bobRows = tx.execute(s -> {
            rls.bind(alice.workspace().id(), alice.user().id());
            return jdbc.queryForObject("SELECT count(*) FROM core.memberships WHERE workspace_id = ?",
                    Long.class, bob.workspace().id());
        });
        assertThat(bobRows).isZero();

        assertThatThrownBy(() -> tx.executeWithoutResult(s -> {
            rls.bind(alice.workspace().id(), alice.user().id());
            jdbc.update("INSERT INTO core.memberships (workspace_id, user_id, role, email) VALUES (?, ?, 'MEMBER', 'x@acme.com')",
                    bob.workspace().id(), alice.user().id());
        })).rootCause().hasMessageContaining("violates row-level security policy");

        Integer renamed = tx.execute(s -> {
            rls.bind(alice.workspace().id(), alice.user().id());
            return jdbc.update("UPDATE core.workspaces SET name = 'pwned' WHERE id = ?", bob.workspace().id());
        });
        assertThat(renamed).isZero();
    }

    @Test
    void tenantDoesNotLeakIntoTheNextTransactionOnThePooledConnection() {
        Long inside = tx.execute(s -> {
            rls.bind(alice.workspace().id(), alice.user().id());
            return jdbc.queryForObject("SELECT count(*) FROM core.workspaces", Long.class);
        });
        assertThat(inside).isEqualTo(1);

        String leftover = tx.execute(s -> jdbc.queryForObject(
                "SELECT coalesce(current_setting('app.workspace_id', true), '')", String.class));
        Long after = tx.execute(s -> jdbc.queryForObject("SELECT count(*) FROM core.workspaces", Long.class));
        assertThat(leftover).isEmpty();
        assertThat(after).isZero();
    }

    @Test
    void tenantIsClearedAfterRollback() {
        assertThatThrownBy(() -> tx.executeWithoutResult(s -> {
            rls.bind(alice.workspace().id(), alice.user().id());
            throw new IllegalStateException("rollback");
        })).hasMessage("rollback");

        Long after = tx.execute(s -> jdbc.queryForObject("SELECT count(*) FROM core.workspaces", Long.class));
        assertThat(after).isZero();
    }

    @Test
    void rlsContextRequiresATransaction() {
        assertThatThrownBy(() -> rls.bind(alice.workspace().id(), alice.user().id()))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void coreAppRoleIsConfinedToCoreSchema() {
        assertThat(jdbc.queryForObject("SELECT current_user", String.class)).isEqualTo("sopilot_core_app");
        assertThat(jdbc.queryForObject("SELECT has_schema_privilege('rag', 'USAGE')", Boolean.class)).isFalse();
        assertThat(jdbc.queryForObject("SELECT has_schema_privilege('core', 'CREATE')", Boolean.class)).isFalse();
        assertThat(jdbc.queryForObject(
                "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user", Boolean.class)).isFalse();
        assertThatThrownBy(() -> jdbc.execute("CREATE TABLE core.not_allowed (id int)"))
                .rootCause().hasMessageContaining("permission denied for schema core");
        assertThatThrownBy(() -> jdbc.execute("ALTER TABLE core.workspaces DISABLE ROW LEVEL SECURITY"))
                .rootCause().hasMessageContaining("must be owner");
    }

    @Test
    void personalWorkspaceHelperIsNotExecutableByOtherRoles() {
        assertThat(jdbc.queryForObject(
                "SELECT has_function_privilege('sopilot_ai_app', 'core.create_personal_workspace(uuid, uuid, text, text)', 'EXECUTE')",
                Boolean.class)).isFalse();
        assertThat(jdbc.queryForObject(
                "SELECT has_function_privilege('public', 'core.create_personal_workspace(uuid, uuid, text, text)', 'EXECUTE')",
                Boolean.class)).isFalse();
        assertThat(jdbc.queryForObject(
                "SELECT prosecdef FROM pg_proc WHERE proname = 'create_personal_workspace'", Boolean.class)).isTrue();
    }

    @Test
    void personalWorkspaceHelperIsIdempotent() {
        UUID again = tx.execute(s -> jdbc.queryForObject("SELECT core.create_personal_workspace(?, ?, 'x', 'x@acme.com')",
                UUID.class, alice.user().id(), UUID.randomUUID()));

        assertThat(again).isEqualTo(alice.workspace().id());
    }

    private static ExternalIdentityClaims dev(String email) {
        return new ExternalIdentityClaims("sopilot-dev", email, email, null, null, null);
    }
}
