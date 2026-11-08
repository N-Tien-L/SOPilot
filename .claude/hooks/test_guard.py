"""Self-test for guard.py: `python .claude/hooks/test_guard.py` (exit 0 = all cases behave)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).with_name("guard.py")
ROOT = str(Path(__file__).resolve().parents[2])
MIG = os.path.join(ROOT, "infrastructure", "db", "migrations", "core")

CASES: list[tuple[str, str, dict, int]] = [
    # (label, tool, tool_input, expected exit code: 2 = blocked, 0 = allowed)
    ("read .env", "Read", {"file_path": os.path.join(ROOT, ".env")}, 2),
    ("read nested .env.local", "Read", {"file_path": os.path.join(ROOT, "frontend", "web", ".env.local")}, 2),
    ("read .env.example", "Read", {"file_path": os.path.join(ROOT, ".env.example")}, 0),
    ("write .env", "Write", {"file_path": os.path.join(ROOT, ".env"), "content": "X=1"}, 2),
    ("grep in .env", "Grep", {"pattern": "KEY", "path": os.path.join(ROOT, ".env")}, 2),
    ("glob .env*", "Glob", {"pattern": "**/.env.*"}, 2),
    ("edit committed migration", "Edit",
     {"file_path": os.path.join(MIG, "V001__core_bootstrap.sql"), "old_string": "a", "new_string": "b"}, 2),
    ("write new migration", "Write", {"file_path": os.path.join(MIG, "V999__new_table.sql"), "content": ""}, 0),
    ("read committed migration", "Read", {"file_path": os.path.join(MIG, "V001__core_bootstrap.sql")}, 0),
    ("edit ordinary file", "Edit", {"file_path": os.path.join(ROOT, "README.md")}, 0),
    ("cat .env", "Bash", {"command": "cat .env"}, 2),
    ("Get-Content .env", "PowerShell", {"command": "Get-Content ./services/core-api/.env"}, 2),
    ("cp .env.example", "Bash", {"command": "diff .env.example docs/x.md"}, 0),
    ("compose down -v", "Bash", {"command": "docker compose -f docker-compose.v2.yml down -v"}, 2),
    ("compose down --volumes", "PowerShell", {"command": "docker-compose down --volumes"}, 2),
    ("compose down", "Bash", {"command": "docker compose -f docker-compose.v2.yml down"}, 0),
    ("compose up -d", "Bash", {"command": "docker compose -f docker-compose.v2.yml up -d"}, 0),
    ("volume prune", "Bash", {"command": "docker volume prune -f"}, 2),
    ("system prune", "PowerShell", {"command": "docker system prune"}, 2),
    ("flyway clean via compose service", "Bash", {"command": "docker compose run flyway-core clean"}, 2),
    ("flyway migrate via compose", "Bash", {"command": "docker compose -f docker-compose.v2.yml run flyway-core migrate"}, 0),
    ("flyway clean direct", "Bash", {"command": "flyway -url=x clean"}, 2),
    ("psql drop schema", "Bash",
     {"command": "docker exec sopilot-v2-postgres psql -U postgres -c 'DROP SCHEMA core CASCADE'"}, 2),
    ("psql truncate", "PowerShell", {"command": "psql -c \"truncate core.users\""}, 2),
    ("grep for TRUNCATE in code", "Bash", {"command": "grep -rn TRUNCATE services/"}, 0),
    ("psql select", "Bash", {"command": "docker exec sopilot-v2-postgres psql -U postgres -c '\\du'"}, 0),
    ("uv venv path", "Bash", {"command": "ls eval/.venv/Scripts"}, 0),
    ("node process.env", "Bash", {"command": "node -e \"console.log(process.env.HOME)\""}, 0),
    ("powershell $env:", "PowerShell", {"command": "$env:SOPILOT_PROFILE = 'local'"}, 0),
]


def run(tool: str, tool_input: dict) -> int:
    event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": ROOT}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), text=True,
                          capture_output=True, env=env, timeout=20).returncode


def main() -> int:
    failures = 0
    for label, tool, tool_input, expected in CASES:
        got = run(tool, tool_input)
        ok = got == expected
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {label}: exit {got} (expected {expected})")
    bad_input = subprocess.run([sys.executable, str(HOOK)], input="not json", text=True,
                               capture_output=True, timeout=20).returncode
    print(f"{'ok  ' if bad_input == 1 else 'FAIL'} malformed input fails open: exit {bad_input}")
    failures += bad_input != 1
    print(f"{len(CASES) + 1 - failures}/{len(CASES) + 1} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
