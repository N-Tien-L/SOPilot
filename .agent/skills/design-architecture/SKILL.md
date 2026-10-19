---
name: design-architecture
description: Producing Technical Design Documents (TDD), Sequence Diagrams, Database Schemas, API Contracts, and Architecture Decision Records (ADR).
version: 1.0.0
author: SOPilot Team
---

# Design Architecture Skill

This skill guides the AI Agent in transforming product requirements (`PRD-*.md`) into robust, enterprise-grade **Technical Design Documents (TDD)** and **Architecture Decision Records (ADR)** aligned with the SOPilot polyglot microservice architecture.

---

## When to use this skill
- After a PRD has been completed (`docs/01-requirements/PRD-*.md`).
- Before decomposing tasks into tickets or writing code.
- When evaluating structural decisions, data ownership, or inter-service contracts.

---

## Core Instructions

### 1. Service Ownership & Domain Mapping (DDD)
- Consult `.agent/context/service-boundaries/responsibilities.md`.
- Determine the **System of Record (Single Owner)** for every new entity:
  - `core` (`auth-service`, `user-service`): Users, credentials, departments, roster.
  - `knowledge` (`knowledge-service`): Documents, versions, files, chunks.
  - `metadata` (`metadata-service`): Tags, categories, access rules.
  - `analytics` (`feedback-service`): Feedback, audits, metrics.
  - `conversation` (`ai-qa-service`): Chat history, citations.
  - Stateless worker (`ingestion-service`): OCR, chunking, embeddings.
- **Rule:** Never allow cross-schema foreign keys in PostgreSQL. Decouple via UUIDs and RabbitMQ events.

### 2. Data Modeling & Schema DDL
- Draft clean, additive PostgreSQL 16 DDL:
  - Table name, typed columns (`UUID`, `VARCHAR`, `TIMESTAMPTZ`, `JSONB`).
  - Strict constraints (`NOT NULL`, `CHECK`, `UNIQUE INDEX`).
  - Updated timestamp triggers (`updated_at`).
  - Target migration path: `infrastructure/init-db/0XX_xxx.sql`.

### 3. Séquence Flow Modeling (Mermaid)
- Create an executable Mermaid `sequenceDiagram` detailing the end-to-end request flow:
  - Client (Next.js) ➔ Gateway (:3001) ➔ Target Service (:808X) ➔ PostgreSQL / RabbitMQ.
  - Show headers propagation (`X-User-Id`, `X-User-Role`, `X-Trace-Id`).

### 4. API Contract & DTO Design
- Format: RESTful versioned endpoints (`/api/v1/...`).
- Detail exact Request / Response JSON payloads.
- Specify HTTP status codes (200, 201, 400, 401, 403, 404, 409).
- Specify gateway reverse proxy routes and RBAC guards (`@Roles(...)`).

### 5. Architectural Decision Records (ADR)
- For every non-trivial decision (trade-offs between performance, maintainability, or data ownership):
  - Generate an ADR in `docs/02-architecture/adr/ADR-<num>-<name>.md` following `docs/02-architecture/adr/templates/adr-template.md`.
  - Include: Context, Decision Drivers, Considered Options, Chosen Outcome & Rationale, Pros/Cons.

### 6. Output Generation
- Follow the template at `docs/02-architecture/designs/templates/tech-design-template.md`.
- Save the file at:
  `docs/02-architecture/designs/TECH-<id>-<short-name>.md`
- Ensure complete YAML frontmatter linking to the PRD.

---

## Next Step Handoff
Once the Technical Design and ADRs are generated:
- Hand off to **`plan-and-decompose`** to generate the Milestone Plan and Task Tickets.
