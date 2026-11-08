# Technical Context Index (`.agent/`)

> **Notice:** This project was originally codenamed *Poliwise* and has been unified under the product name **SOPilot**.
> PostgreSQL database is named `sopilot` (user: `sopilot`). V1 schemas: `core`, `metadata`, `knowledge`, `conversation`, `analytics`; V2 uses `core` and `rag`.

> **2026-11-08: agent configuration moved to Claude Code.** The entry point is [`CLAUDE.md`](../CLAUDE.md). Rules live in `.claude/rules/` (path-scoped), workflows in `.claude/skills/`, the reviewer in `.claude/agents/`, guardrails in `.claude/settings.json` + `.claude/hooks/`. The old `.agent/rules/`, `.agent/skills/`, `AGENTS.md` and `GEMINI.md` were removed (still in git history). Only the technical context remains here.

---

## 🧭 Directory Index

```text
.agent/
├── README.md               # [THIS FILE]
└── context/                # Long-lived technical context (contracts, schema, events, RBAC)
    ├── README.md           # Context index & task -> file lookup table
    ├── overview.md         # Monorepo layout, service responsibilities, Docker topology (V1)
    ├── architecture/       # System overview, flows, feature design, frontend architecture
    ├── service-boundaries/ # Responsibilities, API contracts, events, ownership matrix
    ├── database/           # Schema isolation, ERD diagram, table specifications (core.md, rag.md hold V2)
    ├── authorization/      # RBAC matrix, dual strategy, Google admission, v2-core-identity.md
    ├── storage/            # Document lifecycle & MinIO
    └── patterns/           # Cross-stack quick reference
```

Files with a "V1 LEGACY" banner describe the frozen V1 stack; V2-17 rewrites them.

---

## 📜 Sources of Truth

| What | Where |
|---|---|
| Entry point, architecture, guardrails, workflow, commands | [`CLAUDE.md`](../CLAUDE.md), `.claude/` |
| Specs, plans, ticket status, reports; frontmatter & status conventions | [`docs/README.md`](../docs/README.md), `docs/0*-*/` |
| Contracts, schema, events, RBAC, storage | `.agent/context/` |
| Scripts | `scripts/` |

If you modify REST endpoints, DB schemas, events, RBAC permissions or service contracts, update the matching file in `.agent/context/` in the same change and list the updated docs in your response.
