# Safety Guardrails & Operational Constraints

Strict operational boundaries and safety rules that AI coding agents MUST ALWAYS follow, especially when operating in automated or Turbo mode.

---

## 1. Workspace Boundary & File System Protection

- **Workspace Scoping**:
  - All file operations (create, modify, delete) MUST strictly reside within the repository root (the directory that contains `AGENTS.md` and `.agent/`).
  - Operating on, modifying, or deleting files outside the project root is **STRICTLY FORBIDDEN**.
- **Forbidden Target Paths**:
  - Root drive paths: `C:\`, `D:\`, `/`, etc.
  - Windows system folders: `C:\Windows`, `C:\Program Files`, `C:\Program Files (x86)`.
  - User profile folders outside this repository: `C:\Users\Tien\AppData`, `C:\Users\Tien\Desktop`, `C:\Users\Tien\Documents`, `C:\Users\Tien\.ssh`, `C:\Users\Tien\.aws`.
  - Core project governance directories: `.git/` metadata (do not delete or corrupt git internal objects) and `.agent/` (unless explicitly instructed to update rules/skills).
- **Destructive Deletion Blacklist**:
  - **NEVER** run recursive root or wildcard deletions:
    - `rm -rf /`, `rm -rf *`, `rm -rf .*`
    - `Remove-Item -Recurse -Force /`, `Remove-Item -Recurse -Force *`, `Remove-Item -Recurse -Force C:\*`
    - `del /f /s /q *.*`
  - **Explicit Targets Only**: When cleaning temporary files, logs, or build caches (`target/`, `node_modules/`, `.pytest_cache/`, `dist/`), ALWAYS specify the exact, fully-qualified relative or absolute directory path. Never use blanket wildcards.

---

## 2. Git & Version Control Safety

- **No Force Pushing**:
  - **NEVER** run `git push --force` or `git push -f` on any shared branches (`main`, `master`, `develop`, `release/*`, `staging`).
- **No Unsafe State Wipes**:
  - **NEVER** execute `git reset --hard` if there are uncommitted user changes in the working tree, unless specifically approved or preceded by `git stash`.
  - **NEVER** execute `git clean -fdx` indiscriminately. This command wipes untracked files including local `.env` files, configuration secrets, and uncommitted mock data.
- **Pre-action Inspection**:
  - Check `git status` before performing branching, committing, or checking out branches to avoid unintended work tree overwrites.

---

## 3. Secrets & Credentials Protection

- **No Secret Exposure**:
  - Never print, echo, or log secret keys, credentials, or private keys to stdout/console (e.g., `GROQ_API_KEY`, `EMBEDDING_API_KEY`, JWT secrets, DB passwords).
- **Environment File Isolation**:
  - Ensure `.env` and `.env.local` files remain ignored in `.gitignore`.
  - Never stage or commit `.env` files to git repositories. Always use `.env.example` with placeholder values for documentation.

---

## 4. Container & Database Integrity

- **Preserve Volumes**:
  - **NEVER** run `docker system prune --volumes -f` or `docker volume prune -f`.
  - **NEVER** append `-v` or `--volumes` to `docker compose down` unless the user explicitly requests a total database and storage wipe. Doing so deletes persistent PostgreSQL (`pgvector`), MinIO object storage, and Redis state.
- **Database Safety**:
  - **NEVER** execute destructive DDL commands (`DROP DATABASE`, `DROP SCHEMA`, `TRUNCATE TABLE`) against live running application databases.
  - Schema migrations must be additive and non-destructive whenever possible.

---

## 5. Process & Execution Control

- **No Infinite Loops or Fork Bombs**:
  - Do not execute scripts or commands that spawn unbound child processes or infinite loops without an exit condition.
- **Timeout Management**:
  - Always apply sensible timeouts (`WaitMsBeforeAsync`) for builds, tests, and network requests to prevent hanging processes.
