"""FR-19 at the database layer: three workspaces, both application roles, every tenant table (V2-14).

The service layers add their own checks (core-api: ``TenantIsolationApiIT``; ai-service: retrieval tests).
These tests need only the real migrations, the real roles and real rows, so they stay valid as services change.
Tables are discovered from the catalog: a new tenant table is covered without editing this file, and a new
table that is not tenant-scoped fails ``test_only_reviewed_tables_are_global`` until it is listed on purpose.
"""
from __future__ import annotations

import uuid

import psycopg
import pytest
from psycopg import errors

import isolation
from isolation import Table, tenant

CORE_KINDS = ("department", "category", "document_title", "document_description", "file_name", "outbox",
              "audit", "invitation_email")
RAG_KINDS = ("access_title", "chunk", "term", "conversation", "question", "feedback", "snippet")
# Rows each tenant owns in each seeded table (see conftest).
SEEDED = {
    "core.workspaces": 1, "core.memberships": 1, "core.departments": 1, "core.categories": 1,
    "core.documents": 1, "core.document_versions": 1, "core.outbox_events": 1, "core.audit_logs": 1,
    "core.invitations": 1, "rag.document_access": 1, "rag.chunks": 1, "rag.chunk_terms": 1,
    "rag.conversations": 1, "rag.messages": 1, "rag.message_feedback": 1, "rag.message_citations": 1,
}


@pytest.fixture(params=["core", "rag"])
def layer(request, core_app, ai_app, migrator):
    """(schema, connection of the role that owns it, tenant tables of that schema, secret kinds)."""
    tables = [t for t in isolation.tenant_tables(migrator) if t.schema == request.param]
    if request.param == "core":
        return "core", core_app, tables, CORE_KINDS
    return "rag", ai_app, tables, RAG_KINDS


# ---- schema-level rules -----------------------------------------------------------------------------

def test_tenant_tables_are_discovered_from_the_catalog(migrator):
    names = {t.qualified for t in isolation.tenant_tables(migrator)}

    assert set(SEEDED) <= names
    assert len(names) >= 25, "discovery found suspiciously few tenant tables"


def test_every_tenant_table_enables_and_forces_rls(migrator):
    assert isolation.tables_without_forced_rls(migrator, isolation.tenant_tables(migrator)) == []


def test_only_reviewed_tables_are_global(migrator):
    found = isolation.tables_without_workspace_column(migrator)

    # Flyway history tables exist only when Flyway (not this test's plain runner) applied the migrations.
    assert found <= set(isolation.GLOBAL_TABLES), f"unreviewed non-tenant tables: {found - isolation.GLOBAL_TABLES}"
    assert {"core.users", "core.external_identities", "rag.embedding_cache", "rag.system_usage",
            "rag.processed_requests"} <= found


def test_no_policy_opens_rows_to_an_application_role(migrator):
    rows = migrator.execute(
        "SELECT schemaname || '.' || tablename, policyname, roles, qual, with_check FROM pg_policies "
        "WHERE schemaname IN ('core', 'rag')").fetchall()
    assert rows, "no policies found"
    for table, policy, roles, qual, check in rows:
        if qual == "true" or check == "true":
            # Only the schema owner may match everything; SECURITY DEFINER helpers need that (V003).
            assert set(roles) == {"sopilot_migrator"}, f"{table}.{policy} is open to {roles}"
        else:
            assert "current_workspace" in (qual or "") or "current_app_user" in (qual or ""), \
                f"{table}.{policy} does not tie rows to the tenant: {qual}"


def test_security_definer_helpers_are_reachable_only_by_their_own_service(migrator):
    rows = migrator.execute(
        "SELECT n.nspname, p.proname, p.oid, pg_get_userbyid(p.proowner), p.proconfig "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname IN ('core', 'rag') AND p.prosecdef").fetchall()
    assert rows, "expected SECURITY DEFINER helpers"
    other = {"core": "sopilot_ai_app", "rag": "sopilot_core_app"}
    for schema, name, oid, owner, config in rows:
        assert owner == "sopilot_migrator", f"{schema}.{name} owner {owner}"
        assert any(c.startswith("search_path=") for c in (config or [])), f"{schema}.{name} has no pinned search_path"
        assert not migrator.execute("SELECT has_function_privilege('public', %s, 'EXECUTE')", (oid,)).fetchone()[0], \
            f"{schema}.{name} executable by PUBLIC"
        assert not migrator.execute("SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                                    (other[schema], oid)).fetchone()[0], f"{schema}.{name} reachable by {other[schema]}"


def test_application_roles_are_confined_to_their_schema_and_cannot_bypass_rls(core_app, ai_app):
    for conn, own, foreign in ((core_app, "core", "rag"), (ai_app, "rag", "core")):
        assert conn.execute("SELECT has_schema_privilege(%s, 'USAGE')", (own,)).fetchone()[0]
        assert not conn.execute("SELECT has_schema_privilege(%s, 'USAGE')", (foreign,)).fetchone()[0]
        assert not conn.execute("SELECT has_schema_privilege(%s, 'CREATE')", (own,)).fetchone()[0]
        assert not conn.execute("SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user"
                                ).fetchone()[0]
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(f"ALTER TABLE {own}.{'workspaces' if own == 'core' else 'chunks'} DISABLE ROW LEVEL SECURITY")


def test_a_role_cannot_read_the_other_services_schema(core_app, ai_app, tenants):
    with pytest.raises(errors.InsufficientPrivilege):
        core_app.execute("SELECT count(*) FROM rag.chunks")
    with pytest.raises(errors.InsufficientPrivilege):
        ai_app.execute("SELECT count(*) FROM core.documents")


# ---- no or forged tenant context ------------------------------------------------------------------

def test_no_tenant_context_sees_nothing(layer, tenants):
    _, conn, tables, _ = layer
    with tenant(conn, None):
        assert {t.qualified: isolation.count(conn, t) for t in tables if isolation.count(conn, t)} == {}


def test_a_workspace_that_does_not_exist_sees_nothing(layer, tenants):
    _, conn, tables, _ = layer
    with tenant(conn, str(uuid.uuid4())):
        assert {t.qualified: isolation.count(conn, t) for t in tables if isolation.count(conn, t)} == {}


def test_user_context_without_workspace_sees_no_tenant_rows_except_own_memberships(tenants, core_app, ai_app):
    a = tenants[0]
    with tenant(core_app, None, a.user_id):
        visible = {t.qualified: isolation.count(core_app, t)
                   for t in isolation.tenant_tables(core_app) if t.schema == "core" and isolation.count(core_app, t)}
    # core.memberships and core.workspaces list "my workspaces" by user (TECH §4.2); nothing else.
    assert set(visible) <= {"core.memberships", "core.workspaces"}
    assert visible.get("core.memberships") == 1
    with tenant(ai_app, None, a.user_id):
        assert all(isolation.count(ai_app, t) == 0 for t in isolation.tenant_tables(ai_app) if t.schema == "rag")


def test_a_malformed_workspace_id_is_an_error_never_rows(layer, tenants):
    _, conn, tables, _ = layer
    for bad in ("not-a-uuid", "00000000-0000-0000-0000-00000000000g", "*"):
        with pytest.raises(errors.DataError):
            with tenant(conn, bad):
                isolation.count(conn, tables[0])


def test_missing_context_cannot_write(core_app, ai_app, tenants):
    a = tenants[0]
    with pytest.raises(errors.InsufficientPrivilege):
        with tenant(core_app, None):
            core_app.execute("INSERT INTO core.departments (id, workspace_id, name) VALUES (%s, %s, 'x')",
                             (str(uuid.uuid4()), a.workspace_id))
    with pytest.raises(errors.InsufficientPrivilege):
        with tenant(ai_app, None):
            ai_app.execute("INSERT INTO rag.conversations (id, workspace_id, user_id, title) VALUES (%s, %s, %s, 'x')",
                           (str(uuid.uuid4()), a.workspace_id, a.user_id))


# ---- a valid tenant context -----------------------------------------------------------------------

def test_each_workspace_sees_only_its_own_rows(layer, tenants):
    _, conn, tables, _ = layer
    for t in tenants:
        assert isolation.foreign_rows(conn, tables, t.workspace_id) == {}, f"workspace {t.key} sees foreign rows"
        with tenant(conn, t.workspace_id):
            for table in tables:
                expected = SEEDED.get(table.qualified)
                if expected is not None:
                    assert isolation.count(conn, table) == expected, f"{t.key} {table.qualified}"


def test_no_secret_of_another_workspace_is_ever_readable(layer, tenants):
    _, conn, tables, kinds = layer
    for viewer in tenants:
        with tenant(conn, viewer.workspace_id, viewer.user_id):
            text = "\n".join(isolation.visible_text(conn, table) for table in tables)
        for kind in kinds:
            assert viewer.secrets[kind] in text, f"{viewer.key} cannot read its own {kind}: seed or query is broken"
        for other in tenants:
            if other is viewer:
                continue
            for kind in kinds:
                assert other.secrets[kind] not in text, f"{viewer.key} read {other.key}'s {kind}"


def test_a_workspace_cannot_insert_rows_for_another(core_app, ai_app, tenants):
    a, b = tenants[0], tenants[1]
    with pytest.raises(errors.InsufficientPrivilege):
        with tenant(core_app, a.workspace_id, a.user_id):
            core_app.execute("INSERT INTO core.departments (id, workspace_id, name) VALUES (%s, %s, 'planted')",
                             (str(uuid.uuid4()), b.workspace_id))
    with pytest.raises(errors.InsufficientPrivilege):
        with tenant(ai_app, a.workspace_id, a.user_id):
            ai_app.execute("INSERT INTO rag.conversations (id, workspace_id, user_id, title) VALUES (%s, %s, %s, 'planted')",
                           (str(uuid.uuid4()), b.workspace_id, a.user_id))
    with pytest.raises(errors.InsufficientPrivilege):
        with tenant(core_app, a.workspace_id, a.user_id):
            core_app.execute("INSERT INTO core.memberships (workspace_id, user_id, role, email) "
                             "VALUES (%s, %s, 'OWNER', 'x@example.test')", (b.workspace_id, a.user_id))


def test_a_workspace_cannot_move_its_row_into_another(core_app, tenants):
    a, b = tenants[0], tenants[1]
    with pytest.raises(errors.InsufficientPrivilege):
        with tenant(core_app, a.workspace_id, a.user_id):
            core_app.execute("UPDATE core.departments SET workspace_id = %s", (b.workspace_id,))


def test_a_workspace_cannot_update_or_delete_another_workspaces_rows(core_app, ai_app, tenants, superuser):
    a, b = tenants[0], tenants[1]
    with tenant(core_app, a.workspace_id, a.user_id):
        assert core_app.execute("UPDATE core.documents SET title = 'pwned' WHERE id = %s",
                                (b.document_id,)).rowcount == 0
        assert core_app.execute("DELETE FROM core.documents WHERE id = %s", (b.document_id,)).rowcount == 0
        assert core_app.execute("UPDATE core.workspaces SET name = 'pwned' WHERE id = %s",
                                (b.workspace_id,)).rowcount == 0
    with tenant(ai_app, a.workspace_id, a.user_id):
        assert ai_app.execute("DELETE FROM rag.chunks WHERE workspace_id = %s", (b.workspace_id,)).rowcount == 0
        assert ai_app.execute("UPDATE rag.message_feedback SET comment = 'pwned' WHERE workspace_id = %s",
                              (b.workspace_id,)).rowcount == 0
        assert ai_app.execute("DELETE FROM rag.conversations WHERE workspace_id = %s",
                              (b.workspace_id,)).rowcount == 0
    # Looked at from outside RLS: B's data is untouched.
    assert superuser.execute("SELECT title FROM core.documents WHERE id = %s", (b.document_id,)).fetchone()[0] \
        == b.secrets["document_title"]
    assert superuser.execute("SELECT count(*) FROM rag.chunks WHERE workspace_id = %s", (b.workspace_id,)
                             ).fetchone()[0] == 1


def test_a_workspace_can_still_change_its_own_rows(core_app, tenants):
    a = tenants[0]
    with tenant(core_app, a.workspace_id, a.user_id):
        assert core_app.execute("UPDATE core.departments SET name = name").rowcount == 1


# ---- connection reuse -----------------------------------------------------------------------------

def test_tenant_never_leaks_into_the_next_transaction_on_the_same_connection(layer, tenants):
    _, conn, tables, _ = layer
    table = next(t for t in tables if t.qualified in SEEDED)
    a = tenants[0]
    with tenant(conn, a.workspace_id):
        assert isolation.count(conn, table) > 0
    with conn.transaction():
        leftover = conn.execute("SELECT coalesce(current_setting('app.workspace_id', true), '')").fetchone()[0]
        assert leftover == ""
        assert isolation.count(conn, table) == 0


def test_tenant_is_cleared_after_a_rollback(layer, tenants):
    _, conn, tables, _ = layer
    table = next(t for t in tables if t.qualified in SEEDED)
    with pytest.raises(RuntimeError):
        with tenant(conn, tenants[0].workspace_id):
            raise RuntimeError("rollback")
    with conn.transaction():
        assert isolation.count(conn, table) == 0


def test_alternating_tenants_on_one_connection_never_mix(layer, tenants):
    _, conn, tables, _ = layer
    for _ in range(3):
        for t in tenants:
            assert isolation.foreign_rows(conn, tables, t.workspace_id) == {}


# ---- the detector itself --------------------------------------------------------------------------

def test_detector_finds_the_leak_when_isolation_is_removed(migrator, core_app, tenants):
    """Negative control: the same detectors must light up on a table with no RLS, then go quiet with it."""
    a, b = tenants[0], tenants[1]
    migrator.execute("DROP TABLE IF EXISTS core.canary_notes")
    migrator.execute("CREATE TABLE core.canary_notes (id uuid PRIMARY KEY, workspace_id uuid NOT NULL, body text)")
    try:
        for t in (a, b):
            migrator.execute("INSERT INTO core.canary_notes VALUES (%s, %s, %s)",
                             (str(uuid.uuid4()), t.workspace_id, f"canary-{t.key}"))
        canary = next(t for t in isolation.tenant_tables(migrator) if t.name == "canary_notes")

        assert isolation.tables_without_forced_rls(migrator, [canary]) == ["core.canary_notes"]
        leaks = isolation.foreign_rows(core_app, [canary], a.workspace_id)
        assert leaks == {"core.canary_notes": 1}, "detector missed a table that has no RLS"
        with tenant(core_app, a.workspace_id):
            assert "canary-B" in isolation.visible_text(core_app, canary)

        migrator.execute("ALTER TABLE core.canary_notes ENABLE ROW LEVEL SECURITY")
        migrator.execute("ALTER TABLE core.canary_notes FORCE ROW LEVEL SECURITY")
        migrator.execute("CREATE POLICY tenant_isolation ON core.canary_notes "
                         "USING (workspace_id = core.current_workspace()) "
                         "WITH CHECK (workspace_id = core.current_workspace())")

        assert isolation.tables_without_forced_rls(migrator, [canary]) == []
        assert isolation.foreign_rows(core_app, [canary], a.workspace_id) == {}
        with tenant(core_app, a.workspace_id):
            assert "canary-B" not in isolation.visible_text(core_app, canary)
    finally:
        migrator.execute("DROP TABLE IF EXISTS core.canary_notes")


def test_detector_flags_a_policy_that_opens_a_table(migrator, tenants):
    """A policy of ``USING (true)`` for an application role would pass a naive RLS-enabled check."""
    migrator.execute("DROP TABLE IF EXISTS core.canary_open")
    migrator.execute("CREATE TABLE core.canary_open (id uuid PRIMARY KEY, workspace_id uuid NOT NULL)")
    try:
        migrator.execute("ALTER TABLE core.canary_open ENABLE ROW LEVEL SECURITY")
        migrator.execute("ALTER TABLE core.canary_open FORCE ROW LEVEL SECURITY")
        migrator.execute("CREATE POLICY open_to_all ON core.canary_open USING (true)")
        opened = [r for r in migrator.execute(
            "SELECT policyname, roles, qual FROM pg_policies WHERE tablename = 'canary_open'").fetchall()
            if r[2] == "true" and set(r[1]) != {"sopilot_migrator"}]
        assert opened, "an open policy for PUBLIC must be reported"
    finally:
        migrator.execute("DROP TABLE IF EXISTS core.canary_open")


def _unused(_: Table | psycopg.Connection) -> None:  # keeps imports honest for type checkers
    return None
