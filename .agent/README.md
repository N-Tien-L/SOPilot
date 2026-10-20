# AI Agent Guide & Repository Index

> **Notice:** This project was originally codenamed *Poliwise* and has been unified under the product name **SOPilot**.
> PostgreSQL database is named `sopilot` (user: `sopilot`). The application schemas are strictly partitioned by domain: `core`, `metadata`, `knowledge`, `conversation`, `analytics`.

This directory (`.agent/`) holds the rules, technical context and skills for AI coding agents working in the SOPilot monorepo. The entry point, system topology, guardrails, spec-driven workflow and common commands are in [`AGENTS.md`](../AGENTS.md); this file only indexes what lives here.

---

## 🧭 Directory Index

```text
.agent/
├── README.md               # [THIS FILE] Index of rules, context and skills
├── rules/                  # Mandatory coding standards & constraints
│   ├── general.md          # Working rules, per-stack commands, verification
│   ├── safety-guardrails.md# Absolute guardrails (volume protection, secret prevention)
│   └── frontend.md         # Next.js 16, React 19, Tailwind 4, Zustand, React Query standards
├── context/                # Long-lived technical context (contracts, schema, events, RBAC)
│   ├── README.md           # Context index & task -> file lookup table
│   ├── overview.md         # Monorepo layout, service responsibilities, Docker topology
│   ├── architecture/       # System overview, flows, feature design, frontend architecture
│   ├── service-boundaries/ # Responsibilities, API contracts, RabbitMQ events, ownership matrix
│   ├── database/           # Schema isolation, ERD diagram, table specifications
│   ├── authorization/      # RBAC matrix, dual strategy, Google admission
│   ├── storage/            # Document lifecycle & MinIO
│   └── patterns/           # Cross-stack quick reference
└── skills/                 # Specialized skills (load only the one that matches the work)
    ├── analyze-requirements/ # PRDs (docs/01-requirements/)
    ├── design-architecture/  # TECH designs & ADRs (docs/02-architecture/)
    ├── plan-and-decompose/   # Plans & tickets (docs/03-plans/)
    ├── execute-ticket/       # Ticket implementation playbook
    ├── write-test/           # Test authoring standards, patterns and references
    ├── run-test/             # Running suites & pre-commit verification
    ├── analyze-quality/      # Coverage gaps, audits (docs/04-reports/)
    ├── code-review/          # Self-review and peer-review checklist
    ├── debug-and-diagnose/   # Cross-service debugging & root-cause analysis
    ├── repo-contributing/    # Branching, conventional commits, PRs, releases
    ├── nestjs-gateway/       # NestJS 11 gateway proxy, guards, logging
    ├── springboot-backend/   # Spring Boot 3, Java 17, JPA, OpenFeign patterns
    ├── python-backend/       # FastAPI, pgvector and async patterns
    └── nextjs-frontend/      # Frontend design, state and API integration patterns
```

---

## 📜 Sources of Truth

| What | Where |
|---|---|
| Entry point, topology, guardrails, workflow, commands | [`AGENTS.md`](../AGENTS.md) |
| Specs, plans, ticket status, reports; frontmatter & status conventions | [`docs/README.md`](../docs/README.md), `docs/0*-*/` |
| Contracts, schema, events, RBAC, storage | `.agent/context/` |
| Coding rules & standards | `.agent/rules/` |
| Task playbooks | `.agent/skills/` |
| Scripts | `scripts/` (skills reference these; they do not keep their own copies) |

If you modify REST endpoints, DB schemas, events, RBAC permissions or service contracts, update the matching file in `.agent/context/` in the same change and list the updated docs in your response.
