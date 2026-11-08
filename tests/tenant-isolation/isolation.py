"""Leak detectors shared by the tests and by their own negative control (V2-14).

A detector answers "what can this tenant context see that is not its own". The test suite asserts it
finds nothing on the real schema; ``test_detector_*`` assert it finds something when isolation is
removed, so a green run cannot come from a detector that never looks at anything.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass

import psycopg
from psycopg import sql

TENANT_SCHEMAS = ("core", "rag")

# Tables that are global by design and carry no workspace_id. A new table that is not tenant-scoped
# must be added here on purpose, which forces a review (ADR-005, ADR-007 §4.5).
GLOBAL_TABLES = frozenset({
    "core.users",                 # identity is global; a user belongs to many workspaces
    "core.external_identities",   # (issuer, subject) -> user
    "core.flyway_schema_history",
    "rag.embedding_cache",        # vectors keyed by content hash, never returns text (ADR-007 §4.5)
    "rag.system_usage",           # system-wide counters only
    "rag.processed_requests",     # idempotency keys of /internal/** (UUIDs only, TECH-V2-ai-service §3.5)
    "rag.flyway_schema_history",
})
# Tenant table whose workspace column is called ``id``.
WORKSPACE_TABLE = "core.workspaces"


@dataclass(frozen=True)
class Table:
    schema: str
    name: str
    column: str  # the column that holds the workspace id

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def ident(self) -> sql.Composed:
        return sql.SQL("{}.{}").format(sql.Identifier(self.schema), sql.Identifier(self.name))


def base_tables(conn: psycopg.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_schema = ANY(%s) AND table_type = 'BASE TABLE' ORDER BY 1, 2",
        (list(TENANT_SCHEMAS),)).fetchall()
    return [(s, n) for s, n in rows]


def tenant_tables(conn: psycopg.Connection) -> list[Table]:
    """Every base table of ``core``/``rag`` that holds tenant data, found from the catalog."""
    with_column = {(s, n) for s, n in conn.execute(
        "SELECT table_schema, table_name FROM information_schema.columns "
        "WHERE table_schema = ANY(%s) AND column_name = 'workspace_id'", (list(TENANT_SCHEMAS),)).fetchall()}
    tables = [Table(s, n, "workspace_id") for s, n in base_tables(conn) if (s, n) in with_column]
    schema, name = WORKSPACE_TABLE.split(".")
    tables.append(Table(schema, name, "id"))
    return sorted(tables, key=lambda t: t.qualified)


def tables_without_workspace_column(conn: psycopg.Connection) -> set[str]:
    tenant = {t.qualified for t in tenant_tables(conn)}
    return {f"{s}.{n}" for s, n in base_tables(conn)} - tenant


def tables_without_forced_rls(conn: psycopg.Connection, tables: list[Table]) -> list[str]:
    bad = []
    for t in tables:
        enabled, forced = conn.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relname = %s",
            (t.schema, t.name)).fetchone()
        if not (enabled and forced):
            bad.append(t.qualified)
    return bad


@contextlib.contextmanager
def tenant(conn: psycopg.Connection, workspace_id: str | None, user_id: str | None = None) -> Iterator[None]:
    """One transaction with the RLS variables set the way the services set them (``is_local``)."""
    with conn.transaction():
        conn.execute("SELECT set_config('app.workspace_id', %s, true), set_config('app.user_id', %s, true)",
                     (workspace_id or "", user_id or ""))
        yield


def count(conn: psycopg.Connection, table: Table, only_foreign_of: str | None = None) -> int:
    """Rows visible in the current transaction; with ``only_foreign_of`` only rows of other tenants."""
    query = sql.SQL("SELECT count(*) FROM {}").format(table.ident)
    params: tuple = ()
    if only_foreign_of is not None:
        query = sql.SQL("SELECT count(*) FROM {} WHERE {} IS DISTINCT FROM %s::uuid").format(
            table.ident, sql.Identifier(table.column))
        params = (only_foreign_of,)
    return conn.execute(query, params).fetchone()[0]


def visible_text(conn: psycopg.Connection, table: Table) -> str:
    """Every visible row of the table rendered as text, to search for another tenant's secret."""
    rows = conn.execute(sql.SQL("SELECT t::text FROM {} t").format(table.ident)).fetchall()
    return "\n".join(r[0] for r in rows)


def foreign_rows(conn: psycopg.Connection, tables: list[Table], workspace_id: str) -> dict[str, int]:
    """Per table, how many rows of other workspaces the current role can see in this workspace context."""
    leaks: dict[str, int] = {}
    with tenant(conn, workspace_id):
        for t in tables:
            n = count(conn, t, only_foreign_of=workspace_id)
            if n:
                leaks[t.qualified] = n
    return leaks
