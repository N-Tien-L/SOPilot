---
name: spec-docs
description: Write or update SOPilot spec-chain documents in docs/ (PRD, ADR, TECH design, PLAN, ticket, AUDIT/HANDOFF report), in Vietnamese with the repo's frontmatter and status rules. Use when asked to draft requirements, record an architecture decision, design, plan or split tickets, or write an acceptance/audit report. Not for code changes.
---

# SOPilot spec documents

The source of conventions is `docs/README.md` (frontmatter fields, status vocabulary, PLAN counters, meaning of `done`). Read it first; do not redefine it here.

## Which document

| Need | Type | Location | Template |
|---|---|---|---|
| Problem, scope, acceptance criteria | PRD | `docs/01-requirements/PRD-*.md` | `01-requirements/templates/prd-template.md` |
| Hard-to-reverse decision | ADR | `docs/02-architecture/adr/ADR-NNN-*.md` | `adr/templates/adr-template.md` |
| DDL, API, sequence, config | TECH | `docs/02-architecture/designs/TECH-*.md` | `designs/templates/tech-design-template.md` |
| Tickets, DAG, status table | PLAN + tickets | `docs/03-plans/` | `03-plans/templates/{plan,ticket}-template.md` |
| Evidence of acceptance | AUDIT / HANDOFF | `docs/04-reports/AUDIT-<scope>-<name>-YYYY-MM-DD.md` | `04-reports/templates/audit-report-template.md` |

Chain: PRD `approved` → ADR/TECH → PLAN → tickets → code → AUDIT. No PLAN without an approved PRD.

## Rules

- Prose in Vietnamese; identifiers, paths, commands and code in English. Concise: decisions, numbers, file paths.
- `author: "Owner"`. Never name Claude or any AI as author or co-author.
- Status changes to `approved`/`done`/`final` are the owner's decision. You may propose them. Ticket `done` requires evidence (`docs/README.md`).
- Changing a ticket's status updates the PLAN table **and** its counters in the same edit. Keep `depends_on` ↔ `blocks` ↔ the PLAN DAG consistent.
- An owner decision recorded in PLAN goes in a dated note `> **Owner chốt YYYY-MM-DD (...):** ...` and names every ticket it changes.
- V2 architecture is fixed by ADR-004 to ADR-008 (two services, workspace tenancy + RLS, providers and local-only environment, departments/visibility, Docling). A design that contradicts them needs a new or amending ADR, not a silent change.
- Settled facts live in their ADR/TECH. Link to them; do not copy them into new docs.
- An AUDIT lists the commands actually run with their results, what was not verified, and a verdict. Never claim a test passed that was not run in this work.

## Verify before finishing

- Frontmatter: required fields `id`, `title`, `status`, `created`, `updated`, plus the type-specific fields from `docs/README.md`.
- Relative links resolve. Check every new link path exists.
- For PLAN/ticket edits, recount: `completed_tickets` = number `done`, `review_tickets` = number `review`, `implemented_tickets` = their sum, all matching ticket frontmatter.

## Done when

The document follows its template and `docs/README.md`, links resolve, counters match, and the summary to the user lists which documents changed and which decisions still need the owner.
