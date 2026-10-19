---
name: repo-contributing
description: Standards and workflows for branching, conventional commits, pull requests, semantic versioning, and milestone releases in the SOPilot repository.
version: 1.0.0
author: SOPilot Team
---

# SOPilot Repository Contributing & Git Workflow Skill

This skill enforces professional, enterprise-grade Git workflows, branching conventions, and release procedures for the **SOPilot** microservices project.

---

## When to use this skill
- When starting work on any new feature, bug fix, or refactor.
- When committing code, creating branches, or preparing Pull Requests.
- When performing pre-push validation and build sanity checks.
- When tagging releases or merging milestone releases from `develop` into `main`.

---

## Core Principles & Branching Strategy

The repository follows a **Dual-Trunk Workflow (Main + Develop)** tailored for solo developers and small teams to maintain strict production stability while enabling fast iteration.

### 1. Permanent Branches
- **`main` (Production Branch):**
  - Represents stable, production-ready code deployed on live servers/VPS.
  - **Golden Rule:** **NEVER commit directly to `main`**. All changes to `main` must come from milestone release PRs from `develop` or emergency hotfixes.
  - Every merge into `main` must be tagged with a Semantic Version (`vX.Y.Z`).
- **`develop` (Integration / Staging Branch):**
  - The default working branch for daily development.
  - All feature branches branch off from `develop` and merge back into `develop`.

---

## Branch Naming Conventions

All short-lived working branches must be created from `develop` using standard prefixes:

| Prefix | Usage | Example |
| :--- | :--- | :--- |
| `feat/` | New user-facing or backend features | `feat/jit-onboarding`, `feat/excel-roster-import` |
| `fix/` | Bug fixes and patches | `fix/sse-reconnect-error`, `fix/token-expiration` |
| `perf/` | Performance optimizations | `perf/hybrid-search-ranking`, `perf/jvm-serial-gc` |
| `refactor/` | Code refactoring without behavior change | `refactor/api-client-endpoints` |
| `docs/` | Specs, plans and reports (see `docs/README.md`) | `docs/01-requirements`, `docs/02-architecture`, `docs/03-plans`, `docs/04-reports` |
| `chore/` | Build scripts, dependencies, Docker, configs | `chore/update-dependencies`, `chore/docker-compose-vps` |

### Branch Lifecycle:
```bash
# Always start from fresh develop
git checkout develop
git pull origin develop
git checkout -b feat/<feature-name>

# When done and verified, push and create PR into develop
git push -u origin feat/<feature-name>
```

---

## Commit Standards (Conventional Commits)

Commit messages must follow the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short summary in imperative mood>

[optional body explaining motivation / context]

[optional footer: Closes #123]
```

### 1. Allowed Types:
- `feat`: A new feature
- `fix`: A bug fix
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Code change that improves performance
- `docs`: Documentation only changes
- `chore`: Changes to build process, auxiliary tools, or libraries
- `test`: Adding missing tests or correcting existing tests

### 2. Standard Scopes:
- `gateway`: API Gateway (NestJS)
- `auth`: Authentication Service
- `user`: User & Department Service
- `knowledge`: Knowledge & Document Service
- `metadata`: Metadata & Categories Service
- `feedback`: Feedback & Analytics Service
- `ai-qa`: AI Q&A Retrieval & Streaming Engine
- `ingestion`: Document Ingestion & Chunking Pipeline
- `web`: Next.js Frontend
- `infra`: Docker Compose, DB migrations, Nginx, Redis, RabbitMQ

### 3. Examples:
```bash
git commit -m "feat(auth): implement JIT employee roster verification"
git commit -m "fix(ai-qa): handle empty vector search results gracefully"
git commit -m "perf(ingestion): batch embedding requests to Jina API"
git commit -m "docs(readme): add microservices architecture diagram"
```

---

## Pre-Push & Sanity Check Checklist

Before pushing any branch or opening a PR, the agent or developer MUST run local validation checks:

```powershell
# 1. Verify Docker Compose configuration
docker compose config --quiet

# 2. Verify API Gateway compilation
cd services/api-gateway
npm run build

# 3. Verify Next.js Web Frontend compilation
cd ../../frontend/web
npm run build

# 4. Verify Python syntax (if Python files modified)
python -m py_compile services/ai-qa-service/src/... services/ingestion-service/src/...
```

---

## Pull Request & Merge Strategy

### 1. Feature PRs (`feat/*` ➔ `develop`):
- Open PR on GitHub targeting base `develop`.
- Perform a **Self-Code Review** on the GitHub "Files Changed" tab to catch unintended artifacts, debug logs, or style inconsistencies.
- Merge using **Squash and Merge** to produce a clean, single-commit history on `develop`.
- Delete the feature branch after merging.

### 2. Milestone Release PRs (`develop` ➔ `main`):
- When a planned milestone is complete and validated:
  1. Open a PR with base `main` and compare `develop`.
  2. PR Title: `Release vX.Y.Z: <Milestone Summary>`.
  3. Include a bulleted changelog in the PR description.
  4. Merge into `main` using **Merge Commit** (or Rebase) to preserve the release milestone.
  5. Create an annotated Git tag on `main`:
     ```bash
     git checkout main
     git pull origin main
     git tag -a vX.Y.Z -m "Release vX.Y.Z: <Description>"
     git push origin vX.Y.Z
     ```

---

## Security & Clean Hygiene Rules
- **NEVER commit `.env` or plain-text secrets.** Always update `.env.example` when introducing new environment variables.
- Never commit build artifacts: `node_modules/`, `.next/`, `target/`, `.venv/`, `__pycache__/`, `*.log`.
- Keep commit histories readable, intentional, and production-ready.
