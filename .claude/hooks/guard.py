"""PreToolUse guard for SOPilot (registered in .claude/settings.json). Stdlib only.

Verdicts
  block  exit 2, reason on stderr (Claude sees it). Used for operations CLAUDE.md prohibits.
  ask    exit 0 with a `permissionDecision: ask` JSON on stdout: the owner is prompted.
  allow  exit 0, no output: normal permission flow applies (this hook never approves anything).

Failure handling is fail-CLOSED: unreadable input, an internal error, or a failing/hanging `git`
call exits 2. settings.json also sets `"onFailure": "block"`, which covers a hook that cannot start.

Checks
  1. Secret files: `.env` / `.env.*` (not `*.example|sample|template`) through file tools and through
     shell tokens that name such a path. Plain text such as `process.env` or a grep pattern is fine.
  2. Committed Flyway migrations (infrastructure/db/migrations/**.sql present in HEAD of the repo that
     contains the file, so worktrees work): file-tool edits and shell writes are blocked.
  3. Destructive Docker/DB operations: block `flyway clean` and DROP/TRUNCATE through psql; ask for
     `down -v`, `volume rm|prune`, `system prune`, `docker rm -v`, `compose rm -v`, DELETE FROM,
     psql -f, recursive deletes, git stash/restore/checkout -- (discarding changes).
  4. Git prohibitions: force push, reset --hard, clean, --no-verify (also `-n`), hooksPath override.
  5. Shell writes to the guard itself and settings (`.claude/hooks`, `.claude/settings*.json`): ask.
  6. `--readonly` (v2-reviewer): shell commands must match a small read-only allowlist.

This is a guardrail against mistakes, not a sandbox. It parses commands into tokens; it does not
evaluate them. Known gaps are listed in docs/quality/ and asserted as GAP cases in test_guard.py.
Self-test: python .claude/hooks/test_guard.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatchcase

FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep", "Glob"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
MIGRATIONS = "infrastructure/db/migrations/"
PROTECTED = (".claude/hooks/", ".claude/settings.json", ".claude/settings.local.json")
GIT_TIMEOUT = float(os.environ.get("SOPILOT_GUARD_GIT_TIMEOUT", "5"))

SAFE_SUFFIX = {"example", "sample", "template"}
SECRET_SAMPLES = (".env", ".env.local", ".env.production", ".env.prod", ".env.dev", ".env.development", ".env.test")
WRAPPERS = {"xargs", "sudo", "env", "command", "time", "nohup", "exec", "call", "start", "start-process"}
SEARCH_TOOLS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "findstr", "select-string", "sls"}
SEARCH_VALUE_OPTS = {"-A", "-B", "-C", "-m", "-t", "-T", "-d", "-g"}  # case-sensitive short options with a value
SEARCH_VALUE_OPTS_LOWER = {"--glob", "--iglob", "--include", "--exclude", "--max-count", "--context", "--type",
                           "--after-context", "--before-context", "-path", "-literalpath", "-include", "-exclude",
                           "-filter"}
MUTATING = {"sed", "mv", "move", "move-item", "mi", "rm", "del", "erase", "rmdir", "rd", "remove-item", "ri",
            "set-content", "sc", "add-content", "ac", "out-file", "tee", "tee-object", "cp", "copy", "copy-item",
            "cpi", "truncate", "new-item", "ni", "rename-item", "rni", "ren", "dd", "install", "patch", "perl",
            "clear-content", "set-itemproperty"}
DDL = re.compile(r"\bdrop\s+(?:database|schema|table|owned|role|user)\b|\btruncate\b", re.IGNORECASE)
DELETE_FROM = re.compile(r"\bdelete\s+from\b", re.IGNORECASE)
REDIRECT_TARGET = re.compile(r">>?\s*[\"']?([^\s\"'|;&<>()]+)")


class GuardError(Exception):
    """Internal failure that must block the call (fail closed)."""


Verdict = tuple[str, str]  # ("block" | "ask", reason)


# ----------------------------------------------------------------------------- tokens

_BOUNDARY = set("()`{},<>")
_SEPARATORS = set(";|&\n")


def segments(cmd: str) -> list[list[str]]:
    """Split a shell command into simple commands made of tokens. Quotes are removed, backslash is
    NOT an escape (Windows paths), so `.e""nv` becomes `.env`."""
    segs: list[list[str]] = []
    toks: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    started = False

    def end_token() -> None:
        nonlocal started
        if started:
            toks.append("".join(buf))
            buf.clear()
            started = False

    def end_segment() -> None:
        end_token()
        if toks:
            segs.append(toks.copy())
            toks.clear()

    for ch in cmd:
        if quote:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in "\"'":
            quote = ch
            started = True
        elif ch in _SEPARATORS:
            end_segment()
        elif ch.isspace() or ch in _BOUNDARY:
            end_token()
        else:
            buf.append(ch)
            started = True
    if quote:  # unbalanced quote: do not let it hide the rest of the command
        return [[t for t in re.split(r"[\s;|&()`{},<>\"']+", cmd) if t]]
    end_segment()
    return segs


def prog(tok: str) -> str:
    name = re.split(r"[\\/]", tok.strip())[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def command_index(toks: list[str], names: set[str]) -> int | None:
    """Index of the program named in `names`, allowing leading wrapper words (xargs, sudo, ...)."""
    for i, t in enumerate(toks):
        p = prog(t)
        if p in names:
            return i
        if p not in WRAPPERS and not t.startswith("-") and "=" not in t:
            return None
    return None


# ----------------------------------------------------------------------------- secrets

def secret_name(name: str) -> bool:
    n = name.split(":")[0].strip().rstrip(". ").lower()  # strips NTFS alternate data streams
    if n == ".env":
        return True
    if n.startswith(".env."):
        return n.rsplit(".", 1)[-1] not in SAFE_SUFFIX
    if n.startswith(".") and any(c in n for c in "*?["):  # `.en*`, `.e?v`, `.[e]nv`
        return any(fnmatchcase(s, n) for s in SECRET_SAMPLES)
    return False


def last_component(path: str) -> str:
    parts = [p for p in re.split(r"[\\/]", path) if p]
    return parts[-1] if parts else ""


def secret_in_path(path: str) -> bool:
    return secret_name(last_component(path))


def secret_in_glob(pattern: str) -> bool:
    return any(secret_name(c) for c in re.split(r"[\\/{},]", pattern) if c)


def pattern_positions(toks: list[str]) -> set[int]:
    """Indexes of tokens that are a search pattern (text, not a path) for grep-like tools."""
    start = 1
    if prog(toks[0]) == "git":
        if "grep" not in toks[1:3]:
            return set()
        start = toks.index("grep") + 1
    elif prog(toks[0]) not in SEARCH_TOOLS:
        return set()
    low = [t.lower() for t in toks]
    if any(t in ("-f", "--file") for t in low[start:]):
        return set()  # pattern file: every operand is a path
    explicit = {i + 1 for i, t in enumerate(low) if t in ("-e", "--regexp", "-regexp", "-pattern") and i + 1 < len(toks)}
    if explicit:
        return explicit
    i = start
    while i < len(toks):
        if toks[i] in SEARCH_VALUE_OPTS or low[i] in SEARCH_VALUE_OPTS_LOWER:
            i += 2  # the value is a glob/number/type, never the pattern
        elif toks[i].startswith("-"):
            i += 1
        else:
            return {i}
    return set()


def secret_in_segment(toks: list[str]) -> str | None:
    skip = pattern_positions(toks)
    for i, tok in enumerate(toks):
        if i in skip:
            continue
        for piece in re.split(r"[=:]", tok):
            if secret_in_path(piece):
                return tok
    return None


# ----------------------------------------------------------------------------- git helpers

def run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise GuardError(f"git is unavailable or timed out ({type(exc).__name__}); cannot verify the target") from exc


def real(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def nearest_dir(path: str) -> str:
    d = os.path.dirname(path)
    while d and not os.path.isdir(d):
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return d or os.getcwd()


def locate(path: str, cwd: str) -> tuple[str, str] | None:
    """(repo toplevel, repo-relative posix path) of `path`, or None outside any git repository."""
    absolute = os.path.abspath(path if os.path.isabs(path) else os.path.join(cwd, path))
    d = nearest_dir(absolute)
    top = run_git(["rev-parse", "--show-toplevel"], d)
    if top.returncode != 0:
        return None
    top_path = top.stdout.decode("utf-8", "replace").strip()
    rel = os.path.relpath(os.path.join(os.path.realpath(d), os.path.relpath(absolute, d)), os.path.realpath(top_path))
    return top_path, rel.replace("\\", "/")


def is_committed_migration(path: str, cwd: str) -> bool:
    if "migrations" not in path.lower() or not path.lower().endswith(".sql"):
        return False
    found = locate(path, cwd)
    if not found:
        return False
    top, rel = found
    if not rel.lower().startswith(MIGRATIONS):
        return False
    # Compare case-insensitively: NTFS would let `v001__X.sql` open the committed `V001__x.sql`.
    listing = run_git(["ls-tree", "-r", "--name-only", "HEAD", "--", MIGRATIONS], top)
    if listing.returncode != 0:
        return False  # no HEAD (empty repository): nothing is committed yet
    names = {n.lower() for n in listing.stdout.decode("utf-8", "replace").splitlines()}
    return rel.lower() in names


def is_protected_config(path: str, cwd: str) -> bool:
    low = path.replace("\\", "/").lower()
    if ".claude" not in low:
        return False
    found = locate(path, cwd)
    if found:
        rel = found[1].lower()
    else:
        rel = low
    return any(rel == p or rel.startswith(p) or rel.endswith("/" + p) for p in PROTECTED)


# ----------------------------------------------------------------------------- shell checks

def has_short_flag(args: list[str], letters: str) -> bool:
    return any(a.startswith("-") and not a.startswith("--") and any(c in a[1:] for c in letters) for a in args)


def git_verdict(toks: list[str]) -> Verdict | None:
    i = 1
    while i < len(toks) and toks[i].startswith("-"):
        opt = toks[i]
        if opt in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            if opt == "-c" and i + 1 < len(toks) and toks[i + 1].lower().startswith("core.hookspath"):
                return "block", "Overriding core.hooksPath bypasses repository hooks."
            i += 2
        else:
            if opt.lower().startswith("--config-env") and "hookspath" in opt.lower():
                return "block", "Overriding core.hooksPath bypasses repository hooks."
            i += 1
    if i >= len(toks):
        return None
    sub, args = toks[i].lower(), toks[i + 1:]
    low = [a.lower() for a in args]
    if sub == "push":
        if (any(a.startswith("--force") or a == "--mirror" or a.startswith("+") for a in low)
                or has_short_flag(args, "f")):
            return "block", "Force push is prohibited (CLAUDE.md constraint 9)."
        if "--no-verify" in low:
            return "block", "--no-verify is prohibited (CLAUDE.md constraint 9)."
    if sub == "reset" and "--hard" in low:
        return "block", "`git reset --hard` is prohibited (CLAUDE.md constraint 9)."
    if sub == "clean":
        return "block", "`git clean` is prohibited (CLAUDE.md constraint 9)."
    if sub == "commit" and ("--no-verify" in low or has_short_flag([a for a in args if not a.startswith("-m")], "n")):
        return "block", "`git commit --no-verify` / `-n` is prohibited (CLAUDE.md constraint 9)."
    if sub == "stash" and not (low and low[0] in ("list", "show")):
        return "ask", "git stash moves changes that may belong to the owner (CLAUDE.md constraint 9)."
    if sub == "restore" and not ("--staged" in low and "--worktree" not in low):
        return "ask", "git restore can discard uncommitted work (CLAUDE.md constraint 9)."
    if sub in ("checkout", "switch") and ("--" in args or "." in args or "-f" in low or "--force" in low
                                         or "--discard-changes" in low):
        return "ask", f"git {sub} here can discard uncommitted work (CLAUDE.md constraint 9)."
    return None


def docker_verdict(toks: list[str], at: int) -> Verdict | None:
    program = prog(toks[at])
    rest = toks[at + 1:]
    value_opts = {"-H", "--host", "--context", "-c", "--config", "-l", "--log-level", "-f", "--file", "-p",
                  "--project-name", "--env-file", "--profile", "--project-directory", "--ansi", "--parallel"}

    def next_word(items: list[str]) -> tuple[str | None, list[str]]:
        i = 0
        while i < len(items):
            if items[i] in value_opts:
                i += 2
            elif items[i].startswith("-"):
                i += 1
            else:
                return items[i].lower(), items[i + 1:]
        return None, []

    if program == "docker-compose":
        sub, args = next_word(rest)
    else:
        sub, args = next_word(rest)
        if sub == "compose":
            sub, args = next_word(args)
    if sub is None:
        return None
    flags = [a for a in args if a.startswith("-")]
    volumes = any(a in ("-v", "--volumes") for a in flags) or has_short_flag(flags, "v")
    if program != "docker-compose" and toks[at + 1:] and sub in ("volume", "system", "container", "rm"):
        nxt, _ = next_word(args)
        if sub == "volume" and nxt in ("rm", "remove", "prune"):
            return "ask", "Deleting Docker volumes destroys the research corpus/eval state (CLAUDE.md constraint 3): owner approval required."
        if sub == "system" and nxt == "prune":
            return "ask", "`docker system prune` can delete volumes (CLAUDE.md constraint 3): owner approval required."
        if (sub == "rm" or (sub == "container" and nxt == "rm")) and volumes:
            return "ask", "`docker rm -v` deletes anonymous volumes: confirm with the owner."
        return None
    if sub == "down" and volumes:
        return "ask", "`compose down -v|--volumes` deletes the Postgres/MinIO volumes (CLAUDE.md constraint 3): owner approval required."
    if sub == "rm" and volumes:
        return "ask", "`compose rm -v` deletes anonymous volumes: confirm with the owner."
    return None


def flyway_clean(toks: list[str]) -> bool:
    for i, t in enumerate(toks):
        if t.startswith("-"):
            continue
        base = prog(t)
        if re.fullmatch(r"flyway[\w:.-]*:clean", t.lower()):
            return True
        if "flyway" in base and any(x.lower() == "clean" for x in toks[i + 1:]):
            return True
    return False


def recursive_delete(toks: list[str]) -> bool:
    i = command_index(toks, {"rm", "rmdir", "rd", "del", "erase", "remove-item", "ri"})
    if i is None:
        return False
    for a in toks[i + 1:]:
        flag = a.split(":")[0].lower()
        if flag in ("--recursive", "/s") or re.fullmatch(r"-r(e(c(u(r(s(e)?)?)?)?)?)?", flag):
            return True
        if a.startswith("-") and not a.startswith("--") and re.search(r"[rR]", a[1:]) and prog(toks[i]) == "rm":
            return True
    return False


def find_delete(toks: list[str]) -> bool:
    return prog(toks[0]) == "find" and any(t in ("-delete", "-exec", "-execdir") for t in toks[1:])


def shell_write_targets(cmd: str, segs: list[list[str]]) -> list[str]:
    """Paths a shell command may write: redirection targets and operands of mutating programs."""
    targets = list(REDIRECT_TARGET.findall(cmd))
    for toks in segs:
        i = command_index(toks, MUTATING)
        if i is None:
            continue
        if prog(toks[i]) in ("sed", "perl") and not has_short_flag(toks[i + 1:], "i") \
                and "--in-place" not in toks[i + 1:]:
            continue  # without -i these only read
        targets += [t for t in toks[i + 1:] if not t.startswith("-")]
    for toks in segs:
        if prog(toks[0]) == "git" and len(toks) > 1 and toks[1].lower() in ("rm", "mv", "checkout", "restore"):
            targets += [t for t in toks[2:] if not t.startswith("-")]
    return targets


# ----------------------------------------------------------------------------- read-only mode

READ_PROGS = {"ls", "dir", "cat", "head", "tail", "wc", "grep", "egrep", "rg", "findstr", "uniq", "pwd", "echo",
              "get-content", "gc", "get-childitem", "gci", "select-string", "sls", "measure-object", "select-object",
              "sort-object", "out-string", "format-table", "format-list", "type", "test-path", "get-location", "diff",
              "tree", "realpath", "stat", "cd", "set-location", "true", "sort"}
GIT_READ = {"status", "diff", "log", "show", "merge-base", "rev-parse", "ls-files", "cat-file", "blame", "shortlog",
            "describe", "grep", "ls-tree", "name-rev", "rev-list", "diff-tree", "show-ref", "reflog"}
BRANCH_READ = {"--list", "-l", "--show-current", "-a", "-r", "-v", "-vv", "--contains", "--merged", "--no-merged"}
SCRIPTS = {"scripts/check-migrations.ps1", "scripts/docs/check-docs.ps1"}
PS_FLAGS = {"-noprofile", "-noninteractive", "-file", "-executionpolicy", "bypass", "-nologo", "-command", "&"}
MVN_ARGS = ("-q", "-b", "test", "-dtest=*", "-dsurefire.failifnospecifiedtests=*", "-dfailifnotests=*")
PYTEST_BAD = ("--junit", "--basetemp", "--html", "-o", "--rootdir", "--confcutdir", "-c")


def readonly_segment(toks: list[str]) -> str | None:
    """None if the segment is an allowed read-only command, else a reason."""
    p = prog(toks[0])
    low = [t.lower() for t in toks]
    args = low[1:]
    if p in ("sort",) and any(a.startswith("-o") for a in args):
        return "sort -o writes a file"
    if p in READ_PROGS:
        return None
    if p == "git":
        i = 1
        while i < len(toks) and toks[i].startswith("-"):
            if toks[i] in ("-c",) or toks[i].lower().startswith(("--git-dir", "--work-tree", "--exec-path")):
                return "git option not allowed in read-only mode"
            i += 2 if toks[i] == "-C" else 1
        if i >= len(toks):
            return None
        sub, rest = low[i], low[i + 1:]
        if any(a.startswith("--output") or a == "-o" for a in rest):
            return "git --output writes a file"
        if sub == "branch":
            return None if all(a in BRANCH_READ or not a.startswith("-") for a in rest) and not any(
                a in ("-d", "-m", "-c") for a in rest) else "only listing branches is allowed"
        return None if sub in GIT_READ else f"git {sub} is not read-only"
    norm = [t.replace("\\", "/").removeprefix("./") for t in toks]
    if p in ("powershell", "pwsh"):
        for j, t in enumerate(norm):
            if t.lower() in SCRIPTS:
                return None if all(x.lower() in PS_FLAGS for x in norm[1:j]) else "unexpected PowerShell arguments"
        return "only the repository check scripts may run through PowerShell"
    if norm[0].lower() in SCRIPTS:
        return None
    if p in ("mvnw", "mvnw.cmd"):
        return None if args and all(any(fnmatchcase(a, pat) for pat in MVN_ARGS) for a in args) and "test" in args \
            else "only `mvnw test` is allowed"
    if p == "uv":
        if args[:1] != ["run"]:
            return "only `uv run ...` is allowed"
        rest = [a for a in args[1:] if a not in ("--extra", "dev")]
        if rest[:2] == ["ruff", "check"]:
            return None if not any(a in ("--fix", "--unsafe-fixes", "--add-noqa", "--fix-only") for a in rest) \
                else "ruff fixes files"
        if rest[:1] == ["pytest"]:
            return None if not any(a.startswith(PYTEST_BAD) for a in rest[1:]) else "pytest option writes files"
        return "only ruff check and pytest may run through uv"
    return f"`{toks[0]}` is not on the read-only allowlist"


# ----------------------------------------------------------------------------- main check

def check(event: dict, readonly: bool = False) -> Verdict | None:
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}
    if not isinstance(data, dict):
        raise GuardError("tool_input is not an object")
    cwd = str(event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    asks: list[Verdict] = []

    if tool in FILE_TOOLS:
        if readonly and tool in WRITE_TOOLS:
            return "block", f"{tool} is not available to a read-only agent."
        paths = [data.get(k) for k in ("file_path", "notebook_path", "path") if data.get(k)]
        globs = [data.get(k) for k in (("pattern",) if tool == "Glob" else ("glob",)) if isinstance(data.get(k), str)]
        for p in paths:
            if secret_in_path(str(p)):
                return "block", (f"{tool} on '{p}' is blocked: .env files hold secrets. Read variable names from "
                                 ".env.example or ask the user for a value.")
        if any(secret_in_glob(g) for g in globs):
            return "block", "Searching .env files is not allowed; use .env.example."
        if tool in WRITE_TOOLS:
            for p in paths:
                if is_committed_migration(str(p), cwd):
                    return "block", (f"'{p}' is a committed Flyway migration: its checksum is already recorded. Add the "
                                     "next V<NNN>__<name>.sql in the same chain instead (skill flyway-migration). If the "
                                     "owner really wants this edit, they make it themselves.")
        return None

    if tool in SHELL_TOOLS:
        cmd = str(data.get("command", ""))
        segs = segments(cmd)
        for toks in segs:
            hit = secret_in_segment(toks)
            if hit:
                return "block", (f"The command names a secret file ('{hit}'). Do not read, print, copy or diff .env "
                                 "files; use .env.example and ask the user for values.")
        for toks in segs:
            gi = command_index(toks, {"git"})
            if gi is not None:
                v = git_verdict(toks[gi:])
                if v and v[0] == "block":
                    return v
                if v:
                    asks.append(v)
            di = command_index(toks, {"docker", "docker-compose"})
            if di is not None:
                v = docker_verdict(toks, di)
                if v and v[0] == "block":
                    return v
                if v:
                    asks.append(v)
            if flyway_clean(toks):
                return "block", "`flyway clean` drops every object in the schema (CLAUDE.md constraint 3)."
            if recursive_delete(toks) or find_delete(toks):
                asks.append(("ask", "Recursive/bulk delete: confirm the exact paths with the owner (constraint 13)."))
        if re.search(r"\b(?:psql|pgcli|usql)\b", cmd, re.IGNORECASE):
            if DDL.search(cmd):
                return "block", ("Destructive DDL (DROP/TRUNCATE) against a database is prohibited. Schema changes are "
                                 "additive Flyway migrations; data resets are the owner's call.")
            if DELETE_FROM.search(cmd):
                asks.append(("ask", "DELETE FROM through psql changes data: confirm with the owner."))
            if any(t in ("-f", "--file") for toks in segs for t in toks) or "<" in cmd:
                asks.append(("ask", "psql is running a SQL file the guard cannot inspect: confirm with the owner."))
        for target in shell_write_targets(cmd, segs):
            if is_committed_migration(target, cwd):
                return "block", f"The command writes to committed migration '{target}' (Flyway checksum). Add a new migration."
            if is_protected_config(target, cwd):
                asks.append(("ask", f"The command writes to '{target}', part of the agent security configuration."))
        if readonly:
            if re.search(r"\$\(|`|<\(|\$\{", cmd) or ">" in re.sub(r"\d?>&\d|\d?>\s*(?:/dev/null|\$null)", "", cmd):
                return "block", "Read-only agent: redirection and command substitution are not allowed."
            for toks in segs:
                why = readonly_segment(toks)
                if why:
                    return "block", f"Read-only agent: {why}."
    if asks:
        return ("block" if readonly else "ask"), asks[0][1]
    return None


def main(argv: list[str]) -> int:
    readonly = "--readonly" in argv
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise GuardError("hook input is not a JSON object")
        verdict = check(event, readonly)
    except Exception as exc:  # fail closed on anything unexpected
        sys.stderr.write(f"guard.py: {type(exc).__name__}: {exc}. Blocking because the guard cannot decide.\n")
        return 2
    if not verdict:
        return 0
    kind, reason = verdict
    if kind == "ask":
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                            "permissionDecision": "ask",
                                                            "permissionDecisionReason": reason}}))
        return 0
    sys.stderr.write("Blocked: " + reason + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
