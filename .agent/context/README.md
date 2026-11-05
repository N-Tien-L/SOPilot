# System Context & Architecture Knowledge Base

> **V2 input scope (owner approved 2026-10-20, narrowed 2026-10-21):** PDF with a text layer and Markdown only; TXT was dropped on 2026-10-21 and DOCX is deferred until after the MVP. The V2 upload contract rejects `.txt`/DOCX with `415`, creates no job and points the user to `.md` or a PDF with a text layer; no server-side conversion and no OCR. One PDF library (chosen in V2-20, ADR-008) feeds a shared structured representation; ai-service renders one canonical Markdown after cleaning, and every chunk/citation offset refers to it. The read-only "Nội dung hệ thống nhận diện" view (PRD-V2 FR-31) opens only when a version is `READY`. Document quota defaults to 50 documents / 200 MB per workspace. Rationale: [AUDIT-markdown-normalization](../../docs/04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md). See [PRD-V2 FR-06](../../docs/01-requirements/PRD-V2-sopilot-mvp.md) and [TECH-V2 core-api](../../docs/02-architecture/designs/TECH-V2-core-api.md). This is the V2 target contract, not a change to the legacy ingestion runtime described below.

This directory houses the comprehensive architectural, domain, schema, and interface contracts for the Poliwise platform. All AI agents must reference these documents as the primary source of truth.

---

## 📚 Context Directory Map

```text
.agent/context/
├── README.md                      # [THIS FILE] Context navigation index
├── overview.md                    # System executive summary, ports, services & Docker
├── architecture/                  # Architectural blueprints & frontend design
│   ├── system-overview.md         # Component diagrams, tech stack, and service flows
│   ├── feature-design.md          # Complete 15-feature domain specifications
│   ├── system-flows.md            # Detailed end-to-end system flows & sequence diagrams
│   └── frontend.md                # Next.js 16 App Router state, store, and layers
├── service-boundaries/            # Inter-service interfaces & contracts
│   ├── responsibilities.md        # Explicit domain ownership for all 9 services
│   ├── api-contracts.md           # Unified REST response envelope & error formats
│   ├── events.md                  # RabbitMQ exchanges, routing keys, and event schemas
│   └── ownership-matrix.md        # Entity & resource ownership cross-matrix
├── database/                      # Data persistence & schema definitions
│   ├── schema.md                  # Database-per-service isolation principles
│   ├── erd.mmd                    # Mermaid Entity-Relationship Diagram (ERD)
│   └── tables/                    # Granular table schemas and column definitions
│       ├── core.md                # Accounts, credentials, departments, profiles
│       ├── knowledge.md           # Documents, chunks, embeddings, processing jobs
│       ├── metadata.md            # Categories, tags, document access rules
│       ├── analytics.md           # User feedback, daily aggregates, audit logs
│       └── conversation.md        # Chats, messages, citations, intent classifications
├── authorization/                 # Security, RBAC & ACL enforcement
│   ├── rbac-matrix.md             # Role-based permissions (USER, MANAGER, ADMIN)
│   └── dual-strategy.md           # Read-optimized ACL pre-flattening for vector search
├── storage/                       # Object storage & file lifecycle
│   ├── document-lifecycle.md      # STAGING -> READY document lifecycle & versioning
│   └── minio.md                   # S3-compatible MinIO bucket setup & presigned URLs
└── patterns/                      # Polyglot architectural design patterns
    └── quick-reference.md         # DTO patterns, error handling, transaction boundaries
```

---

## 🎯 Quick Navigation by Task

| When you are working on... | Consult these context files |
|---|---|
| **Adding a REST endpoint** | `service-boundaries/responsibilities.md`, `service-boundaries/api-contracts.md` |
| **Publishing/consuming RabbitMQ events** | `service-boundaries/events.md`, `service-boundaries/responsibilities.md` |
| **Modifying database tables or queries** | `database/schema.md`, `database/tables/*.md`, `database/erd.mmd` |
| **Updating user permissions or RBAC** | `authorization/rbac-matrix.md`, `authorization/dual-strategy.md` |
| **V2 login, access tokens, JIT, RLS (core-api)** | `authorization/v2-core-identity.md`, `database/tables/core.md` (V2 section) |
| **Handling file uploads or processing** | `storage/document-lifecycle.md`, `storage/minio.md` |
| **Frontend UI, stores, or API integration** | `architecture/frontend.md`, `../rules/frontend.md` |
| **AI Q&A or RAG pipeline** | `architecture/system-overview.md`, `database/tables/conversation.md` |
