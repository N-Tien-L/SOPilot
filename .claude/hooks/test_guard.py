"""Self-test for guard.py: `python .claude/hooks/test_guard.py` (exit 0 = every case behaves).

Everything runs against synthetic hook events and a throwaway git repository (plus a linked worktree)
created in the system temp directory. Nothing touches the real project, Docker or a database.

Expectations: ALLOW = exit 0 with no decision, BLOCK = exit 2, ASK = exit 0 with permissionDecision "ask".
Volume deletion (down -v, volume rm|prune, system prune) is ASK by owner decision; flyway clean and DDL stay BLOCK.
GAP cases document inputs the guard is known NOT to catch; they assert ALLOW so a future fix shows up
as a deliberate test change instead of silently shifting the documented limits.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).with_name("guard.py")
ALLOW, BLOCK, ASK, GAP = "allow", "block", "ask", "gap"
MIG = "infrastructure/db/migrations/core/V001__core_bootstrap.sql"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def make_fixture(base: Path) -> tuple[Path, Path, Path]:
    repo = base / "repo"
    (repo / "infrastructure/db/migrations/core").mkdir(parents=True)
    (repo / ".claude/hooks").mkdir(parents=True)
    (repo / MIG).write_text("CREATE SCHEMA core;\n")
    (repo / ".claude/hooks/guard.py").write_text("# hook\n")
    (repo / ".claude/settings.json").write_text("{}\n")
    (repo / "README.md").write_text("x\n")
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "init"], ["branch", "wt-branch"]):
        subprocess.run([*GIT, *args], cwd=repo, check=True, capture_output=True)
    worktree = base / "worktree"
    subprocess.run([*GIT, "worktree", "add", "-q", str(worktree), "wt-branch"], cwd=repo, check=True, capture_output=True)
    outside = base / "not-a-repo"
    outside.mkdir()
    return repo, worktree, outside


def call(event: dict, env_extra: dict | None = None, readonly: bool = False, stdin: str | None = None,
         cwd: Path | None = None, mode: str | None = None) -> tuple[int, str, str]:
    env = dict(os.environ, **(env_extra or {}))
    mode = "readonly" if readonly else mode
    args = [sys.executable, str(HOOK)] + ([f"--{mode}"] if mode else [])
    r = subprocess.run(args, input=stdin if stdin is not None else json.dumps(event), text=True,
                       capture_output=True, env=env, cwd=cwd, timeout=30)
    return r.returncode, r.stdout, r.stderr


def say(message: str) -> None:
    sys.stdout.write(message + "\n")


def outcome(code: int, out: str) -> str:
    if code == 2:
        return BLOCK
    if code == 0 and '"permissionDecision": "ask"' in out:
        return ASK
    return ALLOW if code == 0 else f"exit{code}"


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="guard-test-"))
    try:
        repo, worktree, outside = make_fixture(base)
        cases: list[tuple[str, str, dict, str]] = []

        def add(label: str, tool: str, tool_input: dict, expected: str) -> None:
            cases.append((label, tool, tool_input, expected))

        def sh(label: str, cmd: str, expected: str, tool: str = "Bash") -> None:
            add(label, tool, {"command": cmd}, expected)

        def p(rel: str) -> str:
            return str(repo / rel)

        # --- secrets through file tools
        for label, tool, ti, exp in [
            ("read .env", "Read", {"file_path": p(".env")}, BLOCK),
            ("read nested .env.local", "Read", {"file_path": p("frontend/web/.env.local")}, BLOCK),
            ("read .env.prod", "Read", {"file_path": p("services/x/.env.prod")}, BLOCK),
            ("read .env with alternate data stream", "Read", {"file_path": p(".env::$DATA")}, BLOCK),
            ("read .env.example", "Read", {"file_path": p(".env.example")}, ALLOW),
            ("read .env.production.example", "Read", {"file_path": p(".env.production.example")}, ALLOW),
            ("read .envrc", "Read", {"file_path": p(".envrc")}, ALLOW),
            ("read src/env.ts", "Read", {"file_path": p("src/env.ts")}, ALLOW),
            ("write .env", "Write", {"file_path": p(".env"), "content": "X=1"}, BLOCK),
            ("edit .env", "Edit", {"file_path": p(".env"), "old_string": "a", "new_string": "b"}, BLOCK),
            ("grep path .env", "Grep", {"pattern": "KEY", "path": p(".env")}, BLOCK),
            ("grep glob .env*", "Grep", {"pattern": "KEY", "glob": ".env*"}, BLOCK),
            ("grep for the text .env is fine", "Grep", {"pattern": r"\.env", "path": p("docs")}, ALLOW),
            ("glob **/.env.*", "Glob", {"pattern": "**/.env.*"}, BLOCK),
            ("glob **/*.ts", "Glob", {"pattern": "**/*.ts"}, ALLOW),
        ]:
            add(label, tool, ti, exp)

        # --- secrets through the shell
        for label, cmd, exp in [
            ("cat .env", "cat .env", BLOCK),
            ("cat nested .env", "cat services/core-api/.env", BLOCK),
            ("Get-Content .\\.env", "Get-Content .\\.env", BLOCK),
            ("Get-Content -LiteralPath", "Get-Content -LiteralPath C:\\x\\.env", BLOCK),
            ("gc glob .en*", 'Get-Content ".en*"', BLOCK),
            ("cat .en?", "cat .en?", BLOCK),
            ("cat .e\"\"nv (quote splitting)", 'cat .e""nv', BLOCK),
            ("git show HEAD:.env", "git show HEAD:.env", BLOCK),
            ("git log -- .env", "git log -p -- .env", BLOCK),
            ("source .env", "source .env && echo ok", BLOCK),
            ("grep -f .env pattern file", "grep -f .env README.md", BLOCK),
            ("rg --glob .env", "rg -g .env KEY .", BLOCK),
            ("cp .env.example .env", "cp .env.example .env", BLOCK),
            ("redirect from .env", "docker run --env-file=.env img", BLOCK),
            ("diff .env.example", "diff .env.example docs/x.md", ALLOW),
            ("git log .env.example", "git log -p -- .env.example", ALLOW),
            ("compose --env-file .env.example", "docker compose --env-file .env.example config --quiet", ALLOW),
            ("node process.env text", "node -e \"process.stdout.write(process.env.HOME)\"", ALLOW),
            ("regex over source for process\\.env", "rg -n 'process\\.env' frontend/web", ALLOW),
            ("rg regex pattern .env", 'rg -n "\\.env" docs', ALLOW),
            ("grep pipe for .env text", "ls -la | grep .env", ALLOW),
            ("Select-String for .env text", 'Select-String -Pattern ".env" -Path docs\\*.md', ALLOW),
            ("PowerShell $env: variable", "$env:SOPILOT_PROFILE = 'local'", ALLOW),
            ("ls eval/.venv", "ls eval/.venv/Scripts", ALLOW),
            (".envrc is not a secret file", "cat services/core-api/.envrc", ALLOW),
            ("GAP: runtime string concatenation", "Get-Content (Join-Path . ('.e'+'nv'))", GAP),
            ("GAP: inline interpreter code", "python -c \"say(open('.e'+'nv').read())\"", GAP),
        ]:
            sh(label, cmd, exp)

        # --- Flyway migrations (file tools)
        for label, tool, ti, exp in [
            ("edit committed migration", "Edit", {"file_path": p(MIG), "old_string": "a", "new_string": "b"}, BLOCK),
            ("write committed migration", "Write", {"file_path": p(MIG), "content": ""}, BLOCK),
            ("edit committed migration with other case", "Edit",
             {"file_path": p(MIG.replace("V001__core_bootstrap", "V001__CORE_Bootstrap")), "old_string": "a",
              "new_string": "b"}, BLOCK),
            ("edit committed migration from the worktree", "Edit",
             {"file_path": str(worktree / MIG), "old_string": "a", "new_string": "b"}, BLOCK),
            ("write a new migration", "Write", {"file_path": p("infrastructure/db/migrations/core/V999__new.sql"),
                                              "content": ""}, ALLOW),
            ("read committed migration", "Read", {"file_path": p(MIG)}, ALLOW),
            ("edit ordinary file", "Edit", {"file_path": p("README.md"), "old_string": "x", "new_string": "y"}, ALLOW),
            ("edit sql outside migrations", "Edit", {"file_path": p("docs/example.sql")}, ALLOW),
        ]:
            add(label, tool, ti, exp)
        # --- Flyway migrations (shell)
        for label, cmd, exp in [
            ("append to committed migration", f"echo x >> {MIG}", BLOCK),
            ("glued redirect", f"echo x>>{MIG}", BLOCK),
            ("sed -i on committed migration", f"sed -i s/a/b/ {MIG}", BLOCK),
            ("Set-Content on committed migration", f"Set-Content -Path {MIG} -Value x", BLOCK),
            ("Remove-Item committed migration", f"Remove-Item {MIG}", BLOCK),
            ("mv committed migration", f"mv {MIG} /tmp/x.sql", BLOCK),
            ("git rm committed migration", f"git rm {MIG}", BLOCK),
            ("sed without -i only reads", f"sed -n 1p {MIG}", ALLOW),
            ("cat committed migration", f"cat {MIG}", ALLOW),
            ("Get-Content committed migration", f"Get-Content {MIG}", ALLOW),
            ("git diff on committed migration", f"git diff -- {MIG}", ALLOW),
            ("new migration via redirect", "echo x > infrastructure/db/migrations/core/V998__new.sql", ALLOW),
        ]:
            sh(label, cmd, exp)

        # --- Docker and databases
        for label, cmd, exp in [
            ("compose down -v", "docker compose down -v", ASK),
            ("compose down --volumes", "docker-compose down --volumes", ASK),
            ("compose down --remove-orphans --volumes", "docker compose down --remove-orphans --volumes", ASK),
            ("compose down -fv (combined flags)", "docker compose down -fv", ASK),
            ("compose down -tv 5", "docker compose down -tv 5", ASK),
            ("compose down with -f file placed before", "docker compose -f x.yml -p y down -v", ASK),
            ("volume prune", "docker volume prune -f", ASK),
            ("volume rm", "docker volume rm sopilot_pg", ASK),
            ("volume ls | xargs volume rm", "docker volume ls -q | xargs docker volume rm", ASK),
            ("system prune", "docker system prune", ASK),
            ("system prune volumes", "docker system prune --volumes -f", ASK),
            ("docker context option before subcommand", "docker --context x volume rm v", ASK),
            ("flyway clean direct", "flyway -url=x clean", BLOCK),
            ("flyway clean via compose service", "docker compose run flyway-core clean", BLOCK),
            ("maven flyway:clean", "./mvnw flyway:clean", BLOCK),
            ("psql drop schema", "docker exec pg psql -U postgres -c 'DROP SCHEMA core CASCADE'", BLOCK),
            ("psql drop  table (double space)", 'docker exec pg psql -c "drop  table x"', BLOCK),
            ("psql truncate", 'psql -c "truncate core.users"', BLOCK),
            ("psql DROP OWNED", 'psql -c "DROP OWNED BY x"', BLOCK),
            ("DDL piped into psql", "echo 'DROP TABLE x' | psql", BLOCK),
            ("psql DELETE FROM", 'psql -c "DELETE FROM core.users"', ASK),
            ("psql -f file", "psql -f wipe.sql", ASK),
            ("docker rm -v", "docker rm -v sopilot-v2-postgres", ASK),
            ("docker rm -fv", "docker rm -fv sopilot-v2-postgres", ASK),
            ("compose rm -v", "docker compose rm -v", ASK),
            ("compose down", "docker compose down", ALLOW),
            ("compose down --remove-orphans", "docker compose down --remove-orphans", ALLOW),
            ("compose up -d", "docker compose up -d postgres flyway-core", ALLOW),
            ("compose ps", "docker compose ps -a", ALLOW),
            ("compose logs -f", "docker compose logs -f --tail 50 postgres", ALLOW),
            ("docker logs", "docker logs sopilot-v2-postgres --tail 100", ALLOW),
            ("docker inspect", "docker inspect sopilot-v2-postgres", ALLOW),
            ("docker volume ls", "docker volume ls", ALLOW),
            ("docker volume inspect", "docker volume inspect sopilot_pg", ALLOW),
            ("docker rm -f container", "docker rm -f sopilot-v2-postgres", ALLOW),
            ("docker run with -v mount", "docker run --rm -v vol:/d alpine ls /d", ALLOW),
            ("docker image prune", "docker image prune -f", ALLOW),
            ("flyway migrate via compose", "docker compose run flyway-core migrate", ALLOW),
            ("mvnw clean verify with flyway property", "./mvnw clean verify -Dflyway.locations=x", ALLOW),
            ("psql select", "docker exec sopilot-v2-postgres psql -U postgres -c '\\du'", ALLOW),
            ("grep TRUNCATE in code", "grep -rn TRUNCATE services/", ALLOW),
            ("psql read query", 'psql -c "select count(*) from core.users"', ALLOW),
            ("GAP: volume wiped through a container", "docker run --rm -v vol:/d alpine rm -rf /d/data", GAP),
            ("GAP: SQL inside a script piped to psql", "cat wipe.sql | psql", GAP),
        ]:
            sh(label, cmd, exp)
        sh("PowerShell compose down -v", "docker-compose down --volumes", ASK, "PowerShell")
        sh("PowerShell volume prune", "docker volume prune -f", ASK, "PowerShell")
        sh("PowerShell psql truncate", 'psql -c "truncate core.users"', BLOCK, "PowerShell")

        # --- git
        for label, cmd, exp in [
            ("push --force", "git push --force", BLOCK),
            ("push -f", "git push -f origin x", BLOCK),
            ("push --force-with-lease", "git push --force-with-lease", BLOCK),
            ("push +refspec", "git push origin +main", BLOCK),
            ("push -fu cluster", "git push -fu origin x", BLOCK),
            ("git -C path push --force", "git -C . push --force", BLOCK),
            ("reset --hard", "git reset --hard HEAD~1", BLOCK),
            ("clean -fd", "git clean -fd", BLOCK),
            ("commit --no-verify", "git commit --no-verify -m x", BLOCK),
            ("commit -n", "git commit -n -m x", BLOCK),
            ("commit -nm cluster", "git commit -nm x", BLOCK),
            ("push --no-verify", "git push --no-verify", BLOCK),
            ("hooksPath override", "git -c core.hooksPath=/dev/null commit -m x", BLOCK),
            ("stash", "git stash", ASK),
            ("stash push", "git stash push -m x", ASK),
            ("restore .", "git restore .", ASK),
            ("checkout -- .", "git checkout -- .", ASK),
            ("checkout .", "git checkout .", ASK),
            ("switch --discard-changes", "git switch --discard-changes main", ASK),
            ("plain push", "git push origin feature/x", ALLOW),
            ("push -u", "git push -u origin feature/x", ALLOW),
            ("commit -m with message", 'git commit -m "fix: not a flag -n inside text"', ALLOW),
            ("commit -am", 'git commit -am "x"', ALLOW),
            ("commit --amend --no-edit", "git commit --amend --no-edit", ALLOW),
            ("stash list", "git stash list", ALLOW),
            ("restore --staged", "git restore --staged x", ALLOW),
            ("checkout -b", "git checkout -b feature/x", ALLOW),
            ("checkout branch", "git checkout develop", ALLOW),
            ("log/diff/status", "git status --short; git diff --stat; git log --oneline -5", ALLOW),
            ("reset --soft", "git reset --soft HEAD~1", ALLOW),
            ("PowerShell push -f", "git push -f", BLOCK),
        ]:
            sh(label, cmd, exp, "PowerShell" if label.startswith("PowerShell") else "Bash")

        # --- recursive deletes (ask) and normal deletes
        for label, cmd, exp, tool in [
            ("rm -rf", "rm -rf build", ASK, "Bash"),
            ("rm -r -f", "rm -r -f build", ASK, "Bash"),
            ("rm -fr", "rm -fr build", ASK, "Bash"),
            ("rm --recursive", "rm --recursive build", ASK, "Bash"),
            ("find -delete", "find . -name '*.tmp' -delete", ASK, "Bash"),
            ("Remove-Item -Recurse", "Remove-Item -Recurse x", ASK, "PowerShell"),
            ("Remove-Item -Force -Recurse", "Remove-Item -Force -Recurse x", ASK, "PowerShell"),
            ("rm -r alias", "rm -r x", ASK, "PowerShell"),
            ("ri -r alias", "ri x -r", ASK, "PowerShell"),
            ("del -Recurse alias", "del -Recurse x", ASK, "PowerShell"),
            ("Remove-Item -Recurse:$true", "Remove-Item x -Recurse:$true", ASK, "PowerShell"),
            ("rd /s", "rd /s /q x", ASK, "PowerShell"),
            ("rm single file", "rm build/out.log", ALLOW, "Bash"),
            ("Remove-Item single file", "Remove-Item x.log", ALLOW, "PowerShell"),
            ("rm -f single file", "rm -f x.log", ALLOW, "Bash"),
        ]:
            sh(label, cmd, exp, tool)

        # --- everyday workflow commands from CLAUDE.md and the skills must keep working
        for label, cmd, tool in [
            ("validate-build", "./scripts/validate-build.ps1 -Scope core", "PowerShell"),
            ("run-tests unit", "./scripts/run-tests.ps1 -Scope core-api -Type unit", "PowerShell"),
            ("run-tests ai-service", "./scripts/run-tests.ps1 -Scope ai-service -Type all", "PowerShell"),
            ("check-migrations", "./scripts/check-migrations.ps1 -BaseRef origin/main", "PowerShell"),
            ("check-docs audit", "./scripts/docs/check-docs.ps1 -Mode audit", "PowerShell"),
            ("pre-commit-check", "./scripts/pre-commit-check.ps1", "PowerShell"),
            ("single maven test", "cd services/core-api; ./mvnw test -Dtest=ClassName#method", "PowerShell"),
            ("maven IT", "./mvnw verify -Dit.test=XIT -Dtest=NoSuchTest -Dsurefire.failIfNoSpecifiedTests=false", "Bash"),
            ("uv pytest", "uv run --extra dev pytest tests/unit/test_x.py::test_name -q", "Bash"),
            ("uv ruff", "uv run --extra dev ruff check", "Bash"),
            ("tenant isolation", "cd tests/tenant-isolation; uv run pytest -v", "PowerShell"),
            ("eval harness", "cd eval; uv sync --extra dev; uv run pytest -q", "PowerShell"),
            ("pnpm lint and build", "pnpm lint && pnpm build", "Bash"),
            ("pnpm exec", "pnpm --dir frontend/web exec tsc --noEmit", "Bash"),
            ("infra up", "docker compose up -d postgres flyway-core flyway-rag minio minio-init",
             "PowerShell"),
            ("infra down", "docker compose down", "PowerShell"),
            ("psql inspection", "docker exec sopilot-v2-postgres psql -U postgres -d sopilot -c \"select 1\"", "Bash"),
            ("git inspection", "git status --short; git diff --cached --name-only; git log --oneline -15", "PowerShell"),
            ("git branch from develop", "git switch -c feat/core-x develop", "PowerShell"),
            ("git add", "git add services/core-api/src", "PowerShell"),
            ("read doc", "Get-Content docs/README.md -TotalCount 40", "PowerShell"),
            ("list files", "Get-ChildItem -Recurse .claude -File", "PowerShell"),
            ("compileall", "python -m compileall -q services/ai-service/src", "PowerShell"),
            ("self-test", "python .claude/hooks/test_guard.py", "PowerShell"),
            ("gh pr view", "gh pr view 12 --json title", "Bash"),
        ]:
            sh("workflow: " + label, cmd, ALLOW, tool)

        # --- the guard and its settings
        for label, tool, ti, exp in [
            ("shell appends to guard.py", "Bash", {"command": "echo x >> .claude/hooks/guard.py"}, ASK),
            ("PowerShell Set-Content settings.json", "PowerShell",
             {"command": "Set-Content .claude/settings.json '{}'"}, ASK),
            ("sed -i settings.json", "Bash", {"command": "sed -i s/a/b/ .claude/settings.json"}, ASK),
            ("remove hooks dir file", "Bash", {"command": "rm .claude/hooks/test_guard.py"}, ASK),
            ("cat guard.py", "Bash", {"command": "cat .claude/hooks/guard.py"}, ALLOW),
            ("run self-test", "Bash", {"command": "python .claude/hooks/test_guard.py"}, ALLOW),
            ("write elsewhere in .claude", "Bash", {"command": "echo x > .claude/rules/new.md"}, ALLOW),
        ]:
            add(label, tool, ti, exp)

        failures = 0
        total = 0

        def verify(label: str, expected: str, code: int, out: str, err: str = "") -> None:
            nonlocal failures, total
            total += 1
            got = outcome(code, out)
            want = ALLOW if expected == GAP else expected
            ok = got == want
            failures += not ok
            say(f"{'ok  ' if ok else 'FAIL'} {label}: {got}{' (known gap)' if expected == GAP else ''}"
                  f"{'' if ok else f' (expected {want}) {err.strip()[:140]}'}")

        for label, tool, ti, expected in cases:
            event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti, "cwd": str(repo)}
            code, out, err = call(event, {"CLAUDE_PROJECT_DIR": str(repo)})
            verify(label, expected, code, out, err)

        # --- not a repository: migration-looking path is not protected, secrets still are
        ev = {"tool_name": "Edit", "tool_input": {"file_path": str(outside / MIG)}, "cwd": str(outside)}
        verify("migration path outside any repo", ALLOW, *call(ev)[:2])
        ev = {"tool_name": "Read", "tool_input": {"file_path": str(outside / ".env")}, "cwd": str(outside)}
        verify("secret outside any repo", BLOCK, *call(ev)[:2])

        # --- failure handling: fail closed
        verify("malformed JSON blocks", BLOCK, *call({}, stdin="not json")[:2])
        verify("empty input blocks", BLOCK, *call({}, stdin="")[:2])
        verify("JSON that is not an object blocks", BLOCK, *call({}, stdin="[1,2]")[:2])
        verify("tool_input of the wrong type blocks", BLOCK,
               *call({"tool_name": "Bash", "tool_input": ["x"]})[:2])
        no_git = {"PATH": str(base / "empty"), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
        (base / "empty").mkdir()
        ev = {"tool_name": "Edit", "tool_input": {"file_path": p(MIG)}, "cwd": str(repo)}
        verify("git missing: migration edit blocks (cannot verify)", BLOCK, *call(ev, no_git)[:2])
        ev = {"tool_name": "Read", "tool_input": {"file_path": p("README.md")}, "cwd": str(repo)}
        verify("git missing: unrelated read still allowed", ALLOW, *call(ev, no_git)[:2])
        ev = {"tool_name": "Edit", "tool_input": {"file_path": p(MIG)}, "cwd": str(repo)}
        verify("git timeout: migration edit blocks", BLOCK, *call(ev, {"SOPILOT_GUARD_GIT_TIMEOUT": "0.000001"})[:2])

        # --- read-only mode (v2-reviewer)
        def ro(label: str, cmd: str, expected: str, tool: str = "Bash") -> None:
            ev = {"tool_name": tool, "tool_input": {"command": cmd}, "cwd": str(repo)}
            verify("read-only: " + label, expected, *call(ev, readonly=True)[:2])

        for label, cmd, exp in [
            ("git diff", "git diff --stat", ALLOW),
            ("git log with pipe", "git log --oneline -5 | head -3", ALLOW),
            ("git merge-base", "git merge-base HEAD develop", ALLOW),
            ("git -C path status", "git -C . status", ALLOW),
            ("git branch --show-current", "git branch --show-current", ALLOW),
            ("grep", "grep -rn needle services", ALLOW),
            ("check-migrations via powershell", "powershell -NoProfile -File ./scripts/check-migrations.ps1", ALLOW),
            ("check-docs script", "./scripts/docs/check-docs.ps1", ALLOW),
            ("mvnw architecture test", "./mvnw -q -B test -Dtest=ArchitectureTest", ALLOW),
            ("ruff check", "uv run --extra dev ruff check", ALLOW),
            ("pytest unit", "uv run --extra dev pytest tests/unit -q", ALLOW),
            ("cd then git", "cd services/core-api && git status", ALLOW),
            ("stream merge then pipe", "git log --oneline 2>&1 | Select-Object -First 5", ALLOW),
            ("redirect write", "echo x > notes.txt", BLOCK),
            ("tee", "git log | tee out.txt", BLOCK),
            ("git commit", 'git commit -m x', BLOCK),
            ("git checkout", "git checkout develop", BLOCK),
            ("git push", "git push", BLOCK),
            ("git branch -D", "git branch -D x", BLOCK),
            ("git diff --output", "git diff --output=patch.txt", BLOCK),
            ("git -c option", "git -c core.pager=x log", BLOCK),
            ("rm", "rm README.md", BLOCK),
            ("mv", "mv a b", BLOCK),
            ("sed -i", "sed -i s/a/b/ README.md", BLOCK),
            ("command substitution", "echo $(rm x)", BLOCK),
            ("backtick", "echo `rm x`", BLOCK),
            ("ruff --fix", "uv run --extra dev ruff check --fix", BLOCK),
            ("uv sync", "uv sync", BLOCK),
            ("mvnw install", "./mvnw install", BLOCK),
            ("docker", "docker compose down", BLOCK),
            ("python -c", "python -c \"open('x','w')\"", BLOCK),
            ("chained write after read", "git status && rm x", BLOCK),
            ("secret still blocked", "cat .env", BLOCK),
            ("PowerShell write", "Set-Content x.txt y", BLOCK),
        ]:
            ro(label, cmd, exp)
        ev = {"tool_name": "Write", "tool_input": {"file_path": p("README.md"), "content": "x"}, "cwd": str(repo)}
        verify("read-only: Write tool", BLOCK, *call(ev, readonly=True)[:2])
        ev = {"tool_name": "Bash", "tool_input": {"command": "git stash"}, "cwd": str(repo)}
        verify("read-only: an ask verdict becomes a block", BLOCK, *call(ev, readonly=True)[:2])

        # --- runner mode (v2-runner): read-only plus build/test/check commands
        def rn(label: str, cmd: str, expected: str, tool: str = "PowerShell") -> None:
            ev = {"tool_name": tool, "tool_input": {"command": cmd}, "cwd": str(repo)}
            verify("runner: " + label, expected, *call(ev, mode="runner")[:2])

        for label, cmd, exp in [
            ("run-tests", "./scripts/run-tests.ps1 -Scope core-api -Type unit", ALLOW),
            ("run-tests piped tail", "./scripts/run-tests.ps1 -Scope ai-service -Type unit 2>&1 | Select-Object -Last 20",
             ALLOW),
            ("run-tests *>&1", "./scripts/run-tests.ps1 -Scope ai-service -Type unit *>&1 | Select-Object -Last 20",
             ALLOW),
            ("validate-build", "./scripts/validate-build.ps1 -Scope web", ALLOW),
            ("pre-commit-check", "./scripts/pre-commit-check.ps1", ALLOW),
            ("check-docs", "./scripts/docs/check-docs.ps1", ALLOW),
            ("powershell -File run-tests", "powershell -NoProfile -File ./scripts/run-tests.ps1 -Scope core-api", ALLOW),
            ("single maven test", "cd services/core-api; ./mvnw test -Dtest=X#y", ALLOW),
            ("maven IT", "./mvnw -q -B verify -Dit.test=XIT -Dtest=NoSuchTest -Dsurefire.failIfNoSpecifiedTests=false",
             ALLOW),
            ("uv pytest", "cd services/ai-service; uv run --extra dev pytest tests/unit -q", ALLOW),
            ("uv ruff check", "uv run --extra dev ruff check", ALLOW),
            ("uv ruff format --check", "uv run --extra dev ruff format --check", ALLOW),
            ("uv sync --locked", "cd eval; uv sync --extra dev --locked; uv run pytest -q", ALLOW),
            ("pnpm lint", "pnpm --dir frontend/web lint", ALLOW),
            ("pnpm test", "pnpm --dir frontend/web test", ALLOW),
            ("pnpm exec tsc", "pnpm --dir frontend/web exec tsc --noEmit", ALLOW),
            ("compose ps", "docker compose ps -a", ALLOW),
            ("compose logs", "docker compose logs --tail 50 postgres", ALLOW),
            ("hook self-test", "python .claude/hooks/test_guard.py", ALLOW),
            ("git diff", "git diff --stat", ALLOW),
            ("uv sync without lock", "uv sync --extra dev", BLOCK),
            ("uv add", "uv add httpx", BLOCK),
            ("ruff --fix", "uv run --extra dev ruff check --fix", BLOCK),
            ("ruff format", "uv run --extra dev ruff format", BLOCK),
            ("pnpm install", "pnpm --dir frontend/web install", BLOCK),
            ("pnpm lint --fix", "pnpm --dir frontend/web lint --fix", BLOCK),
            ("pnpm dev", "pnpm --dir frontend/web dev", BLOCK),
            ("mvnw install", "./mvnw install", BLOCK),
            ("mvnw spring-boot:run", "./mvnw spring-boot:run", BLOCK),
            ("compose up", "docker compose up -d postgres", BLOCK),
            ("compose down", "docker compose down", BLOCK),
            ("docker exec", "docker exec pg psql -c 'select 1'", BLOCK),
            ("git commit", "git commit -m x", BLOCK),
            ("redirect write", "./scripts/run-tests.ps1 -Scope core-api > out.txt", BLOCK),
            ("chained write", "./scripts/pre-commit-check.ps1; rm x", BLOCK),
            ("python -c", "python -c \"print(1)\"", BLOCK),
            ("secret still blocked", "cat .env", BLOCK),
        ]:
            rn(label, cmd, exp)
        ev = {"tool_name": "Edit", "tool_input": {"file_path": p("README.md"), "old_string": "x", "new_string": "y"},
              "cwd": str(repo)}
        verify("runner: Edit tool", BLOCK, *call(ev, mode="runner")[:2])

        # --- coder mode (v2-coder): edits allowed, git/deps/status files are not
        def cd(label: str, tool: str, ti: dict, expected: str) -> None:
            ev = {"tool_name": tool, "tool_input": ti, "cwd": str(repo)}
            verify("coder: " + label, expected, *call(ev, {"CLAUDE_PROJECT_DIR": str(repo)}, mode="coder")[:2])

        def cs(label: str, cmd: str, expected: str) -> None:
            cd(label, "PowerShell", {"command": cmd}, expected)

        for label, tool, ti, exp in [
            ("edit source", "Edit", {"file_path": p("services/core-api/src/X.java"), "old_string": "a",
                                     "new_string": "b"}, ALLOW),
            ("write new test", "Write", {"file_path": p("services/ai-service/tests/unit/test_x.py"), "content": ""},
             ALLOW),
            ("write new migration", "Write", {"file_path": p("infrastructure/db/migrations/core/V999__x.sql"),
                                              "content": ""}, ALLOW),
            ("edit .env.example", "Edit", {"file_path": p(".env.example"), "old_string": "a", "new_string": "b"}, ALLOW),
            ("edit design doc", "Edit", {"file_path": p("docs/architecture/x.md"), "old_string": "a",
                                         "new_string": "b"}, ALLOW),
            ("edit committed migration", "Edit", {"file_path": p(MIG), "old_string": "a", "new_string": "b"}, BLOCK),
            ("edit pom.xml", "Edit", {"file_path": p("services/core-api/pom.xml"), "old_string": "a",
                                      "new_string": "b"}, BLOCK),
            ("edit pyproject.toml", "Edit", {"file_path": p("services/ai-service/pyproject.toml"), "old_string": "a",
                                             "new_string": "b"}, BLOCK),
            ("write package.json", "Write", {"file_path": p("frontend/web/package.json"), "content": "{}"}, BLOCK),
            ("edit ticket", "Edit", {"file_path": p("docs/execution/initiatives/v2/tickets/V2-1.md"),
                                     "old_string": "a", "new_string": "b"}, BLOCK),
            ("edit .claude rule", "Edit", {"file_path": p(".claude/rules/core-api.md"), "old_string": "a",
                                           "new_string": "b"}, BLOCK),
            ("read ticket", "Read", {"file_path": p("docs/execution/initiatives/v2/tickets/V2-1.md")}, ALLOW),
            ("read .env", "Read", {"file_path": p(".env")}, BLOCK),
        ]:
            cd(label, tool, ti, exp)
        for label, cmd, exp in [
            ("run-tests", "./scripts/run-tests.ps1 -Scope core-api -Type unit", ALLOW),
            ("single pytest", "cd services/ai-service; uv run --extra dev pytest tests/unit/test_x.py -q", ALLOW),
            ("ruff --fix on own files", "uv run --extra dev ruff check --fix src/x.py", ALLOW),
            ("git status/diff", "git status --short; git diff --stat", ALLOW),
            ("gh pr view", "gh pr view 12", ALLOW),
            ("git add", "git add services", BLOCK),
            ("git commit", "git commit -m x", BLOCK),
            ("git checkout -b", "git checkout -b feat/x", BLOCK),
            ("git switch", "git switch develop", BLOCK),
            ("git push", "git push origin x", BLOCK),
            ("git stash (ask becomes block)", "git stash", BLOCK),
            ("gh pr create", "gh pr create --fill", BLOCK),
            ("uv add", "uv add httpx", BLOCK),
            ("pnpm add", "pnpm --dir frontend/web add zod", BLOCK),
            ("npm install", "npm install", BLOCK),
            ("pip install", "pip install x", BLOCK),
            ("recursive delete (ask becomes block)", "Remove-Item -Recurse build", BLOCK),
            ("redirect into ticket", "echo x > docs/execution/initiatives/v2/tickets/V2-1.md", BLOCK),
            ("Set-Content pom.xml", "Set-Content services/core-api/pom.xml x", BLOCK),
        ]:
            cs(label, cmd, exp)

        say(f"{total - failures}/{total} passed")
        return 1 if failures else 0
    finally:
        # Remove only the temp directory this run created (git worktree files are read-only on Windows).
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
