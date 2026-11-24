"""Module boundaries of ``sopilot_ai`` (TECH-V2-ai-service §4), checked from source with ``ast``.

- ``docproc`` is pure: text in, structure out. No database, HTTP, storage or web framework.
- ``retrieval``, ``providers`` and ``docproc`` never import the HTTP layer or the ingest worker.
- Tenant binding (``set_config('app.workspace_id', ...)``) is written only in ``db/engine.py``.
- Read-access SQL over ``rag.document_access`` is built only by ``retrieval/access_filter.py``;
  writes stay in ``db/repositories``.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2] / "src" / "sopilot_ai"

IO_LIBS = ("sqlalchemy", "psycopg", "fastapi", "httpx", "minio", "starlette")
UPPER_LAYERS = ("sopilot_ai.api", "sopilot_ai.ingest", "sopilot_ai.worker", "fastapi", "starlette")


def _modules(subpackage: str) -> list[Path]:
    return sorted((PKG / subpackage).rglob("*.py"))


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _violations(paths: list[Path], banned: tuple[str, ...]) -> list[str]:
    return [f"{p.relative_to(PKG)} imports {name}"
            for p in paths for name in sorted(_imports(p))
            if any(name == b or name.startswith(b + ".") for b in banned)]


def test_docproc_is_pure() -> None:
    banned = IO_LIBS + tuple(f"sopilot_ai.{m}" for m in
                             ("db", "api", "ingest", "outbox", "retrieval", "providers", "worker"))
    assert _violations(_modules("docproc"), banned) == []


@pytest.mark.parametrize("subpackage", ["retrieval", "providers", "docproc", "qa"])
def test_lower_layers_do_not_import_http_or_worker(subpackage: str) -> None:
    assert _violations(_modules(subpackage), UPPER_LAYERS) == []


def test_rule_based_qa_modules_and_context_assembly_do_no_io():
    """V2-10 deterministic part: no storage or HTTP, so ``eval/`` can import it."""
    paths = [PKG / "retrieval" / "context.py", *_modules("qa")]
    banned = IO_LIBS + ("sopilot_ai.db",)
    assert _violations(paths, banned) == []


def _files_containing(pattern: str) -> set[str]:
    rx = re.compile(pattern, re.IGNORECASE)
    return {p.relative_to(PKG).as_posix() for p in PKG.rglob("*.py")
            if rx.search(p.read_text(encoding="utf-8"))}


def test_tenant_binding_lives_only_in_engine() -> None:
    assert _files_containing(r"set_config\(\s*'app\.workspace_id'") == {"db/engine.py"}


def test_document_access_is_read_only_through_the_access_filter() -> None:
    readers = _files_containing(r"\bFROM\s+rag\.document_access\b|\bJOIN\s+rag\.document_access\b")
    assert readers <= {"retrieval/access_filter.py"}, readers


def test_conversation_sql_is_always_scoped_to_the_workspace_and_the_owner() -> None:
    """V2-10 milestone 3: every statement of the conversation repository names ``workspace_id``,
    and the ones on conversations or messages also name ``user_id`` (a user's own turns only)."""
    source = (PKG / "conversations" / "repository.py").read_text(encoding="utf-8")
    statements = re.findall(r'text\(f?"""(.*?)"""\)', source, re.DOTALL)
    assert len(statements) >= 10
    for sql in statements:
        assert "workspace_id" in sql or ":wid" in sql, sql[:80]
        if re.search(r"rag\.(conversations|messages)\b", sql):
            assert "user_id" in sql, sql[:80]


def test_only_the_repository_writes_conversation_tables() -> None:
    writers = _files_containing(
        r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+rag\.(conversations|messages|message_citations"
        r"|guard_events|usage_counters|system_usage)\b")
    assert writers <= {"conversations/repository.py", "quota/counters.py"}, writers
