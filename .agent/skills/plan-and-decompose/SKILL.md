---
name: plan-and-decompose
description: Creating structured execution plans and decomposing complex requirements into actionable tickets.
version: 1.1.0
author: SOPilot Team
---

# Plan and Decompose Skill

This skill guides the AI Agent in transforming Product Requirements (`PRD-*.md`) and Technical Designs (`TECH-*.md`) into clear, phased **Execution Plans** and finely decomposed, machine-executable **Tickets**.

---

## When to use this skill
- After a PRD (`docs/01-requirements/PRD-*.md`) and Tech Design (`docs/02-architecture/designs/TECH-*.md`) are approved.
- Before beginning implementation on any multi-service milestone or feature.
- When creating roadmap DAGs and ticket backlogs.

---

## Core Instructions

### 1. Ingest Upstream Specifications
- Read the corresponding **PRD** at `docs/01-requirements/PRD-<id>-<name>.md`.
- Read the corresponding **Tech Design** at `docs/02-architecture/designs/TECH-<id>-<name>.md`.
- Check related **ADRs** at `docs/02-architecture/adr/`.
- Ensure all service boundaries and schema ownerships are strictly respected.

### 2. Formulate Execution Phases & Dependency DAG
Organize tickets into a strict, phased dependency order:
- **Phase 1: Database & Foundation**: Additive DDL migrations in `infrastructure/init-db/`.
- **Phase 2: Backend Domain & APIs**: Microservice entities, repositories, business logic, events.
- **Phase 3: Gateway & Client Integration**: API Gateway routing, RBAC guards, Next.js frontend UI.
- **Phase 4: Verification & Audit**: Platform integration testing, smoke tests, quality audit.

### 3. Ticket Decomposition Rules
Break down the work into tickets following `docs/03-plans/templates/ticket-template.md`:
- **Single Unit of Work**: Each ticket must be implementable independently once its `depends_on` are `done`.
- **Scope Discipline**: A single ticket must touch only ONE primary service scope whenever possible (e.g. `user`, `auth`, `gateway`, `web`), except for shared cross-service E2E tests (`platform`).
- **Granular Sizing**:
  - `S` (<2h): Simple schema migration, proxy route, or minor UI tweak.
  - `M` (2-4h): Controller + Service + Repository + Unit Test.
  - `L` (4-8h): Complex workflow, multi-step frontend component + state.
  - `XL` (>8h): **MUST BE SPLIT** into smaller tickets.
- **Checklist Requirements**: Every ticket MUST have:
  - Binary Acceptance Criteria (`- [ ]`).
  - Step-by-step Implementation Guide with exact file paths.
  - Test Requirements and fast verification commands.

### 4. Output Generation
- Create the execution plan file at:
  `docs/03-plans/PLAN-<plan-id>-<short-name>.md`
- Create individual ticket files at:
  `docs/03-plans/tickets/<ticket-id>-<short-name>.md`

---

## References
- Frontmatter & status conventions: [docs/README.md](../../../docs/README.md)
- [Plan Template](../../../docs/03-plans/templates/plan-template.md)
- [Ticket Template](../../../docs/03-plans/templates/ticket-template.md)
- [Complexity Estimation Guide](references/complexity-estimation.md)
- [Dependency Analysis Guide](references/dependency-analysis.md)
