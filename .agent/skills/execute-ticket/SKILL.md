---
name: execute-ticket
description: Skill for implementing a planned ticket in the SOPilot project
version: 1.0.0
author: SOPilot Team
---

# Execute Ticket Skill

## When to use this skill
- When implementing a planned ticket
- When picking up a task from the plan backlog

## Core Instructions

1. **Read & Parse Ticket**
   - Read the ticket file at `docs/03-plans/tickets/<ticket-id>-*.md` (`docs/plans/` is deprecated).
   - Parse the YAML frontmatter to identify `id`, `type`, `scope`, `status`, and `depends_on`.
   - Load the acceptance criteria and implementation guide.

2. **Check Dependencies**
   - Verify all `depends_on` tickets have status `done`.
   - If not, report which dependencies are blocking and stop.

3. **Prepare Workspace**
   - Update the ticket file status from `todo` to `in-progress`.
   - Create a branch following the `repo-contributing` convention: `{type}/{scope}-{short-name}`.
   - Load the relevant coding skill based on the `scope`:
     - `auth`, `user`, `knowledge`, `metadata`, `feedback`: read `springboot-backend` skill.
     - `ai-qa`, `ingestion`: read `python-backend` skill.
     - `gateway`: read `nestjs-gateway` skill.
     - `web`: read `nextjs-frontend` skill.

4. **Implement**
   - Follow the Implementation Guide steps sequentially.
   - For each step:
     - Read existing file context for MODIFY actions.
     - Apply coding standards from the loaded skill.
     - Write clean, production-ready code.

5. **Self-Check**
   - After implementation, walk through each acceptance criteria checkbox.
   - Run the appropriate build/lint command for the service type using `./scripts/validate-build.ps1` or reference table below.
   - Review the diff using `./scripts/check-conventions.ps1` to check for debug artifacts, cross-service changes, etc.

6. **Update Status**
   - Update the ticket file status to `review` after the self-check passes, and update the status table and counters in the parent PLAN.
   - Never set `done` yourself from a passing build: `done` means accepted with evidence after review (see `docs/README.md`).

### Build Commands Reference Table

| Scope | Build Command | Lint Command |
|-------|---------------|--------------|
| auth, user, knowledge, metadata, feedback | `cd services/{scope}-service && ./mvnw compile -q` | (built into compile) |
| ai-qa, ingestion | `cd services/{scope}-service && python -m py_compile src/**/*.py` | `cd services/{scope}-service && uv run ruff check` |
| gateway | `cd services/api-gateway && pnpm build` | `cd services/api-gateway && pnpm lint` |
| web | `cd frontend/web && pnpm build` | `cd frontend/web && pnpm lint` |

## References
- [Service Type Guide](references/service-type-guide.md)
- [Build Validation Script](../../../scripts/validate-build.ps1)
- [Convention Checker Script](../../../scripts/check-conventions.ps1)
