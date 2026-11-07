"""Disposable pgvector Postgres for integration tests.

Starts ``pgvector/pgvector:0.8.0-pg16`` on tmpfs with ``infrastructure/db/init`` (roles,
extension) and applies ``infrastructure/db/migrations/rag`` in order as ``sopilot_migrator``,
like Flyway. No .env is read, no named volume is created, the container is removed afterwards.
The service connects as ``sopilot_ai_app`` (NOBYPASSRLS); assertions use the superuser.
"""
from __future__ import annotations

import secrets
import shutil
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest

REPO = Path(__file__).resolve().parents[4]
IMAGE = "pgvector/pgvector:0.8.0-pg16"


@dataclass(frozen=True)
class Database:
    host: str
    port: int
    password: str

    def url(self, role: str) -> str:
        return f"postgresql://{role}:{self.password}@{self.host}:{self.port}/sopilot"

    def superuser(self) -> psycopg.Connection:
        return psycopg.connect(self.url("postgres"), autocommit=True)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def database() -> Iterator[Database]:
    if not _docker_available():
        pytest.skip("Docker is not available")
    name = f"sopilot-ai-it-{uuid.uuid4().hex[:8]}"
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
        deadline = time.monotonic() + 90
        while True:  # the init scripts run on a socket-only server first; wait for the app role
            try:
                psycopg.connect(db.url("sopilot_ai_app"), connect_timeout=2).close()
                break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(1)
        with psycopg.connect(db.url("sopilot_migrator"), autocommit=True) as conn:
            conn.execute("CREATE SCHEMA rag")
            for path in sorted((REPO / "infrastructure/db/migrations/rag").glob("V*.sql")):
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
        yield db
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture(scope="session")
async def engine(database: Database) -> AsyncIterator:
    from sopilot_ai.db.engine import make_engine

    eng = make_engine(database.url("sopilot_ai_app"))
    yield eng
    await eng.dispose()
