---
title: "V2 SOPilot MVP"
status: approved
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
plan: PLAN-V2-SOPILOT-MVP
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/architecture/decisions/adr-007-departments-member-profiles-document-access.md
  - docs/architecture/decisions/adr-008-pdf-extraction-docling.md
  - docs/architecture/decisions/adr-009-department-publishers.md
  - docs/architecture/components/core-api.md
  - docs/architecture/components/ai-service.md
  - docs/architecture/data/document-access-sync.md
---

# V2 SOPilot MVP

**Goal:** a local, multi-tenant Q&A system over company SOPs with verified citations, measured first (RQ1–RQ5) and handed over as a research report. **Progress:** the status table in [PLAN.md](PLAN.md) (do not repeat it here).

| Read | For |
|---|---|
| [PRD-V2](../../../product/prd-v2-sopilot-mvp.md) | What and why |
| [core-api](../../../architecture/components/core-api.md), [ai-service](../../../architecture/components/ai-service.md), [document access sync](../../../architecture/data/document-access-sync.md) | How (shared architecture docs) |
| [ADR-004](../../../architecture/decisions/adr-004-two-service-architecture.md) … [ADR-009](../../../architecture/decisions/adr-009-department-publishers.md) | Decisions this initiative depends on |
| [PLAN.md](PLAN.md) | Order, dependencies, status |
| [tickets/](tickets/) | Units of work (`V2-01` … `V2-37`) |
| [designs/](designs/) | Initiative-only design notes: [QA guard and defense](designs/qa-guard-and-defense.md), [QA strip and judge](designs/qa-strip-and-judge.md) (companions to ai-service §7.1) |

## Notes
- Ticket ids `V2-NN` and the ticket file prefixes are kept: `eval/sopilot_eval/plan_check.py` parses the PLAN table and the Mermaid edges, and code, CI and migrations cite tickets by id.
- Ticket bodies were translated from Vietnamese on 2026-11-13; quoted Vietnamese sample text (questions, UI strings, document fragments, patterns) is kept as data.

## Closing
When every ticket is `done` (or the plan is `superseded`), set `status: archived` here and on PLAN.md, and move the folder to `docs/archive/initiatives/` in the same change as the link updates.
