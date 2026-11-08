"""PreToolUse guard for SOPilot (wired in .claude/settings.json). Stdlib only.

Blocks (exit 2, reason on stderr, which Claude sees):
  1. Reading or writing .env / .env.* files (except *.example), by file tools or shell commands.
  2. Editing a Flyway migration under infrastructure/db/migrations/ that already exists in HEAD.
  3. Shell commands that delete Docker volumes or data: `docker compose down -v|--volumes`,
     `docker volume rm|prune`, `docker system prune`, `flyway clean`, and DROP DATABASE|SCHEMA|TABLE /
     TRUNCATE sent through psql or `docker exec`.

This is a guardrail against mistakes, not a sandbox: a determined command can bypass it.
Malformed input exits 1 (non-blocking notice) so a broken hook never locks the session.
Self-test: python .claude/hooks/test_guard.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import PurePath

FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep", "Glob"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
MIGRATIONS = "infrastructure/db/migrations/"

# `.env` or `.env.<suffix>` as a path component; `.env.example` is allowed.
ENV_IN_TEXT = re.compile(r"(?<![\w.-])\.env(\.[\w.-]+)?(?![\w-])")
DESTRUCTIVE_SHELL = [
    (re.compile(r"\bdocker(?:-compose|\s+compose)\b[^;&|\n]*\bdown\b[^;&|\n]*\s(?:-v|--volumes)\b"),
     "`docker compose down -v` deletes the Postgres/MinIO volumes. Use `down` without -v."),
    (re.compile(r"\bdocker\s+volume\s+(?:rm|prune)\b"), "Deleting Docker volumes is not allowed."),
    (re.compile(r"\bdocker\s+system\s+prune\b"), "`docker system prune` can delete volumes and images."),
    (re.compile(r"\bflyway\b[^;&|\n]*\bclean\b"), "`flyway clean` drops every object in the schema."),
]
DDL = re.compile(r"\b(?:DROP\s+(?:DATABASE|SCHEMA|TABLE)|TRUNCATE)\b", re.IGNORECASE)
SQL_CLIENT = re.compile(r"\b(?:psql|docker\s+exec|docker\s+compose\b[^;&|\n]*\bexec)\b", re.IGNORECASE)


def env_file_named(text: str) -> str | None:
    for m in ENV_IN_TEXT.finditer(text):
        if (m.group(1) or "").lower() not in (".example", ".example.local"):
            return m.group(0)
    return None


def is_env_path(path: str) -> bool:
    name = PurePath(path.replace("\\", "/")).name.lower()
    return (name == ".env" or name.startswith(".env.")) and not name.endswith(".example")


def project_relative(path: str, root: str) -> str | None:
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root))
    if p != r and not p.startswith(r + os.sep):
        return None
    return os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace("\\", "/")


def committed(rel: str, root: str) -> bool:
    result = subprocess.run(["git", "-C", root, "cat-file", "-e", f"HEAD:{rel}"],
                            capture_output=True, timeout=5)
    return result.returncode == 0


def check(event: dict) -> str | None:
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()

    if tool in FILE_TOOLS:
        paths = [data.get(k) for k in ("file_path", "notebook_path", "path") if data.get(k)]
        for p in paths:
            if is_env_path(p):
                return (f"Blocked: {tool} on '{p}'. .env files hold secrets and are off limits. "
                        "Read variable names from .env.example or ask the user for a value.")
        patterns = [data.get(k) for k in ("glob", "pattern") if isinstance(data.get(k), str)]
        if tool in ("Grep", "Glob") and any(env_file_named(g) for g in patterns):
            return "Blocked: searching .env files is not allowed; use .env.example."
        if tool in WRITE_TOOLS:
            for p in paths:
                rel = project_relative(p, root)
                if rel and rel.startswith(MIGRATIONS) and rel.endswith(".sql") and committed(rel, root):
                    return (f"Blocked: '{rel}' is a committed Flyway migration and may already be applied; "
                            "Flyway checksums forbid editing it. Add the next V<NNN>__<name>.sql in the same "
                            "chain instead (see .claude/skills/flyway-migration). If the owner explicitly "
                            "wants this edit, they must make it themselves.")
        return None

    if tool in SHELL_TOOLS:
        cmd = str(data.get("command", ""))
        hit = env_file_named(cmd)
        if hit:
            return (f"Blocked: the command references '{hit}'. Do not read, print, copy or diff .env files; "
                    "use .env.example for variable names and ask the user for values.")
        for rx, why in DESTRUCTIVE_SHELL:
            if rx.search(cmd):
                return f"Blocked: {why} Ask the user to run it themselves if they really want this."
        if DDL.search(cmd) and SQL_CLIENT.search(cmd):
            return ("Blocked: destructive DDL (DROP DATABASE/SCHEMA/TABLE, TRUNCATE) against a database. "
                    "Schema changes are additive Flyway migrations; data resets are the user's call.")
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"guard.py: unreadable hook input ({exc}); not enforcing\n")
        return 1
    reason = check(event)
    if reason:
        sys.stderr.write(reason + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
