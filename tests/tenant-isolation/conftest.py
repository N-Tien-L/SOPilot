"""Disposable V2 Postgres with the production roles, both Flyway chains and three seeded tenants.

Same recipe as ``docker-compose.v2.yml`` and the service tests: ``pgvector/pgvector:0.8.0-pg16`` on tmpfs,
the real ``infrastructure/db/init`` scripts (roles, extension), then ``infrastructure/db/migrations/core``
and ``.../rag`` in order as ``sopilot_migrator``. No ``.env`` is read and no named volume is touched.

``ISOLATION_MUTATION=disable-rls`` switches RLS off on every tenant table after seeding. The suite must then
FAIL; CI runs it that way and requires the failure (see ``.github/workflows/tenant-isolation.yml``).
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
import pytest

import isolation

REPO = Path(__file__).resolve().parents[2]
IMAGE = "pgvector/pgvector:0.8.0-pg16"
MUTATION = os.environ.get("ISOLATION_MUTATION", "")


@dataclass(frozen=True)
class Database:
    host: str
    port: int
    password: str

    def url(self, role: str) -> str:
        return f"postgresql://{role}:{self.password}@{self.host}:{self.port}/sopilot"

    def connect(self, role: str) -> psycopg.Connection:
        return psycopg.connect(self.url(role), autocommit=True)


@dataclass
class Tenant:
    key: str
    workspace_id: str
    user_id: str
    secrets: dict[str, str] = field(default_factory=dict)
    document_id: str = ""
    version_id: str = ""
    message_id: str = ""


def _docker_available() -> bool:
    return shutil.which("docker") is not None and subprocess.run(
        ["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="session")
def database() -> Iterator[Database]:
    if not _docker_available():
        pytest.skip("Docker is not available")
    name = f"sopilot-tenant-it-{uuid.uuid4().hex[:8]}"
    password = secrets.token_hex(16)
    init_dir = REPO / "infrastructure" / "db" / "init"
    subprocess.run([
        "docker", "run", "-d", "--rm", "--name", name, "--tmpfs", "/var/lib/postgresql/data",
        "-e", "POSTGRES_DB=sopilot", "-e", "POSTGRES_USER=postgres",
        "-e", f"POSTGRES_PASSWORD={password}", "-e", f"V2_DB_MIGRATOR_PASSWORD={password}",
        "-e", f"V2_DB_CORE_APP_PASSWORD={password}", "-e", f"V2_DB_AI_APP_PASSWORD={password}",
        "-v", f"{init_dir}:/docker-entrypoint-initdb.d:ro", "-p", "127.0.0.1::5432", IMAGE,
    ], check=True, capture_output=True)
    try:
        port_line = subprocess.run(["docker", "port", name, "5432/tcp"], check=True,
                                   capture_output=True, text=True).stdout.splitlines()[0]
        db = Database("127.0.0.1", int(port_line.rsplit(":", 1)[1]), password)
        deadline = time.monotonic() + 120
        while True:  # the init scripts run on a socket-only server first; wait for the app role
            try:
                psycopg.connect(db.url("sopilot_core_app"), connect_timeout=2).close()
                break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(1)
        with db.connect("sopilot_migrator") as conn:
            for schema in ("core", "rag"):
                conn.execute(f"CREATE SCHEMA {schema}")
                for path in sorted((REPO / "infrastructure/db/migrations" / schema).glob("V*.sql")):
                    with conn.transaction():
                        conn.execute(path.read_text(encoding="utf-8"))
        yield db
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture(scope="session")
def migrator(database: Database) -> Iterator[psycopg.Connection]:
    with database.connect("sopilot_migrator") as conn:
        yield conn


@pytest.fixture(scope="session")
def core_app(database: Database) -> Iterator[psycopg.Connection]:
    """One long-lived connection as core-api's role, reused by every test (like a pooled connection)."""
    with database.connect("sopilot_core_app") as conn:
        yield conn


@pytest.fixture(scope="session")
def ai_app(database: Database) -> Iterator[psycopg.Connection]:
    with database.connect("sopilot_ai_app") as conn:
        yield conn


@pytest.fixture(scope="session")
def superuser(database: Database) -> Iterator[psycopg.Connection]:
    with database.connect("postgres") as conn:
        yield conn


def _vector(hot: int) -> str:
    return "[" + ",".join("1" if i == hot else "0" for i in range(1024)) + "]"


def _seed_core(conn: psycopg.Connection, t: Tenant) -> None:
    s = t.secrets
    dept, category, version = (str(uuid.uuid4()) for _ in range(3))
    with isolation.tenant(conn, t.workspace_id, t.user_id):
        conn.execute("INSERT INTO core.departments (id, workspace_id, name) VALUES (%s, %s, %s)",
                     (dept, t.workspace_id, s["department"]))
        conn.execute("INSERT INTO core.categories (id, workspace_id, name) VALUES (%s, %s, %s)",
                     (category, t.workspace_id, s["category"]))
        conn.execute("INSERT INTO core.documents (id, workspace_id, title, description, latest_version_id, "
                     "created_by) VALUES (%s, %s, %s, %s, %s, %s)",
                     (t.document_id, t.workspace_id, s["document_title"], s["document_description"], version,
                      t.user_id))
        conn.execute(
            "INSERT INTO core.document_versions (id, workspace_id, document_id, version_no, status, original_name, "
            "mime_type, file_type, size_bytes, sha256, object_key, uploaded_by) "
            "VALUES (%s, %s, %s, 1, 'READY', %s, 'text/markdown', 'MD', 10, %s, %s, %s)",
            (version, t.workspace_id, t.document_id, s["file_name"], secrets.token_bytes(32),
             f"workspaces/{t.workspace_id}/documents/{t.document_id}/versions/{version}", t.user_id))
        conn.execute("UPDATE core.documents SET current_version_id = %s WHERE id = %s", (version, t.document_id))
        conn.execute("INSERT INTO core.outbox_events (id, workspace_id, aggregate_id, event_type, payload) "
                     "VALUES (%s, %s, %s, 'INGEST_REQUESTED', jsonb_build_object('title', %s::text))",
                     (str(uuid.uuid4()), t.workspace_id, t.document_id, s["outbox"]))
        conn.execute("INSERT INTO core.audit_logs (id, workspace_id, actor_id, action, details) "
                     "VALUES (%s, %s, %s, 'DOCUMENT_UPLOADED', jsonb_build_object('title', %s::text))",
                     (str(uuid.uuid4()), t.workspace_id, t.user_id, s["audit"]))
        conn.execute("INSERT INTO core.invitations (id, workspace_id, email, role, token_hash, invited_by, "
                     "expires_at) VALUES (%s, %s, %s, 'MEMBER', %s, %s, now() + interval '7 days')",
                     (str(uuid.uuid4()), t.workspace_id, s["invitation_email"], secrets.token_bytes(32), t.user_id))
    t.version_id = version


def _seed_rag(conn: psycopg.Connection, t: Tenant, hot: int) -> None:
    s = t.secrets
    chunk, conversation, message = (str(uuid.uuid4()) for _ in range(3))
    with isolation.tenant(conn, t.workspace_id, t.user_id):
        conn.execute("INSERT INTO rag.document_access (workspace_id, document_id, visibility, access_revision, "
                     "active_version_id, title) VALUES (%s, %s, 'WORKSPACE', 1, %s, %s)",
                     (t.workspace_id, t.document_id, t.version_id, s["access_title"]))
        conn.execute(
            "INSERT INTO rag.chunks (id, workspace_id, document_id, version_id, ordinal, chunk_type, section_path, "
            "char_start, char_end, content, index_text, token_count, content_sha256, embedding, "
            "embedding_provider, embedding_model, embedding_dim, embedding_revision, lexical_len) "
            "VALUES (%s, %s, %s, %s, 0, 'PROSE', ARRAY['1'], 0, 10, %s, %s, 5, %s, %s::vector, "
            "'local', 'test', 1024, 'r1', 5)",
            (chunk, t.workspace_id, t.document_id, t.version_id, s["chunk"], s["chunk"], secrets.token_bytes(32),
             _vector(hot)))
        conn.execute("INSERT INTO rag.chunk_terms (workspace_id, chunk_id, term, tf) VALUES (%s, %s, %s, 1)",
                     (t.workspace_id, chunk, s["term"].lower()))
        conn.execute("INSERT INTO rag.conversations (id, workspace_id, user_id, title) VALUES (%s, %s, %s, %s)",
                     (conversation, t.workspace_id, t.user_id, s["conversation"]))
        conn.execute("INSERT INTO rag.messages (id, workspace_id, conversation_id, user_id, role, content) "
                     "VALUES (%s, %s, %s, %s, 'USER', %s)",
                     (message, t.workspace_id, conversation, t.user_id, s["question"]))
        conn.execute("INSERT INTO rag.message_feedback (workspace_id, message_id, user_id, vote, comment) "
                     "VALUES (%s, %s, %s, -1, %s)", (t.workspace_id, message, t.user_id, s["feedback"]))
        conn.execute("INSERT INTO rag.message_citations (workspace_id, message_id, n, document_id, version_id, "
                     "char_start, char_end, snippet) VALUES (%s, %s, 1, %s, %s, 0, 10, %s)",
                     (t.workspace_id, message, t.document_id, t.version_id, s["snippet"]))
    t.message_id = message


SECRET_KINDS = ("department", "category", "document_title", "document_description", "file_name", "outbox",
                "audit", "invitation_email", "access_title", "chunk", "term", "conversation", "question",
                "feedback", "snippet")


@pytest.fixture(scope="session")
def tenants(database: Database, migrator: psycopg.Connection, core_app: psycopg.Connection,
            ai_app: psycopg.Connection) -> list[Tenant]:
    """Three workspaces, each owning rows with its own unique 'secret' strings in every seeded table."""
    out: list[Tenant] = []
    for hot, key in enumerate("ABC"):
        t = Tenant(key=key, workspace_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()),
                   document_id=str(uuid.uuid4()))
        t.secrets = {kind: f"SECRET{key}{kind.replace('_', '')}{uuid.uuid4().hex[:8]}" for kind in SECRET_KINDS}
        # Columns with a lower-case CHECK (email) or lower-cased index terms must hold the secret verbatim.
        t.secrets["invitation_email"] = t.secrets["invitation_email"].lower() + "@example.test"
        t.secrets["term"] = t.secrets["term"].lower()
        migrator.execute("INSERT INTO core.users (id, email, display_name) VALUES (%s, %s, %s)",
                         (t.user_id, f"owner-{key.lower()}@example.test", f"Owner {key}"))
        migrator.execute("INSERT INTO core.workspaces (id, name, kind, created_by) VALUES (%s, %s, 'TEAM', %s)",
                         (t.workspace_id, f"Workspace {key}", t.user_id))
        migrator.execute("INSERT INTO core.memberships (workspace_id, user_id, role, email) "
                         "VALUES (%s, %s, 'OWNER', %s)", (t.workspace_id, t.user_id, f"owner-{key.lower()}@example.test"))
        _seed_core(core_app, t)
        _seed_rag(ai_app, t, hot)
        out.append(t)
    return out


@pytest.fixture(scope="session", autouse=True)
def _mutation(tenants: list[Tenant], migrator: psycopg.Connection) -> None:
    """Negative control for CI: with ``ISOLATION_MUTATION=disable-rls`` every test must see a broken system."""
    if MUTATION == "disable-rls":
        for table in isolation.tenant_tables(migrator):
            migrator.execute(f"ALTER TABLE {table.qualified} DISABLE ROW LEVEL SECURITY")
