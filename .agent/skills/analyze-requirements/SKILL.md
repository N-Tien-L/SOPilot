---
name: analyze-requirements
description: Eliciting, structuring, and generating Product Requirements Documents (PRD) and functional specifications for SOPilot features.
version: 1.0.0
author: SOPilot Team
---

# Analyze Requirements Skill

This skill guides the AI Agent in transforming vague or high-level user ideas into crisp, enterprise-grade **Product Requirements Documents (PRD)** and functional specifications.

---

## When to use this skill
- When starting any new feature, milestone, or business requirement.
- When clarifying ambiguous requirements or user stories.
- Before beginning technical architecture or task planning.

---

## Core Instructions

### 1. Requirements Discovery & Elicitation
- Identify the **Problem Statement**: What friction, operational bottleneck, or security risk exists today?
- Identify **Key Personas**:
  - `Employee`: Q&A user, document viewer, searcher.
  - `Manager`: Department-level policy creator, analytics viewer.
  - `Admin / HR`: System configurator, roster manager, permission granter.
- Extract **Use Cases**: Map step-by-step user journeys (Actors, Preconditions, Trigger, Main Flow, Postconditions).

### 2. Formulating Requirements
- **Functional Requirements (FR-xx)**:
  - Write specific, testable, and unambiguous statements.
  - Include validation rules (e.g., email format, duplicate checking, status transitions).
- **Non-Functional Requirements (NFR-xx)**:
  - *RBAC & Security*: Required role (`USER`, `MANAGER`, `ADMIN`), department visibility rules.
  - *Performance*: API latency SLA (e.g., P95 < 500ms, streaming SSE first token < 1.5s).
  - *Data Integrity*: Constraints, idempotency, transaction boundaries.
  - *Audit*: Actions requiring audit log creation in `analytics.audit_logs`.

### 3. Boundary Control (Scope & Out-of-Scope)
- Explicitly delineate **In-Scope** vs **Out-of-Scope**.
- Prevent feature creep and keep implementations focused and deliverable.

### 4. Output Generation
- Follow the template at `docs/01-requirements/templates/prd-template.md`.
- Save the file at:
  `docs/01-requirements/PRD-<milestone/feature-id>-<short-name>.md`
- Ensure complete YAML frontmatter as defined in `docs/README.md` (section "Quy ước frontmatter"):
  ```yaml
  ---
  id: PRD-XXX
  title: "..."
  status: draft
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  milestone: "..."
  priority: P0
  ---
  ```

---

## Next Step Handoff
Once the PRD is created and agreed upon with the user:
- Hand off to **`design-architecture`** to design system topology, data schemas, and API contracts.
