# SOPilot documentation

The persistent knowledge base for SOPilot. Agents start at the root [`CLAUDE.md`](../CLAUDE.md). This page is the map for everyone. It does not repeat document content.

**Precedence when sources disagree:** running code and config → `docs/` → service READMEs. Report the mismatch; never silently "fix" either side.

## Where things live

| Need | Go to |
|---|---|
| What the product must do and why | [`product/`](product/) — PRD-V2 (FR-xx requirements) |
| How the system fits together | [`architecture/system-overview.md`](architecture/system-overview.md) |
| A component's design | [`architecture/components/`](architecture/components/) — core-api (TECH-V2-core-api), ai-service (TECH-V2-ai-service), frontend |
| Roles, tokens, tenancy | [`architecture/domain/identity-and-access.md`](architecture/domain/identity-and-access.md) |
| Schemas, RLS, access sync | [`architecture/data/`](architecture/data/) (migrations in `infrastructure/db/migrations/` are the source) |
| HTTP envelope, errors, endpoint map | [`architecture/api/http-conventions.md`](architecture/api/http-conventions.md); endpoint and env tables live in each service README |
| Why a decision was made | [`architecture/decisions/`](architecture/decisions/) — ADR-001…; superseded ADRs stay in the log |
| Diagrams | [`architecture/diagrams/`](architecture/diagrams/) |
| Current work, status, tickets | [`execution/initiatives/`](execution/initiatives/) — V2 MVP: [`v2-sopilot-mvp/PLAN.md`](execution/initiatives/v2-sopilot-mvp/PLAN.md) |
| Evidence that something was tested | [`quality/test-reports/`](quality/test-reports/) (binaries in `artifacts/testing/`, gitignored) |
| Experiments, evaluations, investigations | [`research/`](research/) |
| Continuing interrupted work | [`handoffs/`](handoffs/) (newest date first) |
| Public project write-up | [`portfolio/`](portfolio/) (not authoritative) |
| History (V1, closed plans, old handoffs) | [`archive/`](archive/) — read-only; may be Vietnamese |
| Starting a new document | [`templates/`](templates/) |

Transitional: `01-requirements/`, `02-architecture/`, `03-plans/`, `04-reports/templates/` and `_archive/` are legacy remnants of the old layout and are removed in the cleanup phase. Do not add to them or link new work to them.

## Conventions

### Language and authorship
English only for active docs. Keep Vietnamese only for quoted source material, UI copy and domain terms whose translation would lose meaning. Archived documents keep their original language. `author: "Owner"` on every document; never an AI name, tool or invented role. Tool-assisted analysis is stated in the body as a method fact.

### Kind is decided by location
| Location | Kind | `id` | `status` |
|---|---|---|---|
| `product/` | PRD | `PRD-…` | draft · approved · superseded · archived |
| `architecture/decisions/` | ADR | `ADR-NNN` | draft · approved · superseded · archived |
| `architecture/{components,data,domain,api}/`, `system-overview.md` | design | `TECH-…` if one exists, else none | draft · approved · superseded · archived |
| `execution/initiatives/*/README.md` | initiative | none | draft · approved · superseded · archived |
| `execution/initiatives/*/PLAN.md` | plan | `PLAN-…` | draft · approved · superseded · archived |
| `execution/initiatives/*/tickets/` | ticket | `V2-NN` (existing) · `TICKET-NNN` (new) | todo · in_progress · review · done · blocked |
| `execution/initiatives/*/designs/` | design | optional | draft · approved · superseded · archived |
| `quality/test-plans/` | test plan | `TEST-PLAN-NNN` | draft · approved · superseded · archived |
| `quality/test-reports/` | test report | `TEST-REPORT-NNN` (existing `AUDIT-…` ids kept) | draft · final |
| `quality/testing-strategy.md`, `quality/quality-gates.md` | guide | none | draft · approved · superseded · archived |
| `operations/` | runbook | none | draft · approved · superseded · archived |
| `research/` | research | `RESEARCH-NNN` (existing `RESEARCH-…`/`AUDIT-…` ids kept) | draft · final · superseded |
| `handoffs/` | handoff | none (existing `HANDOFF-…` kept) | draft · final |
| `archive/` | historical | unchanged | unchanged (not validated) |

Required on every validated doc: `title`, `status`, `created`, `updated` (`YYYY-MM-DD`), `author`. Kind-specific fields are listed in each template (for example `verdict` on test reports, PLAN counters, ticket `depends_on`/`blocks`). Optional on all: `refs` (root-relative paths), `supersedes`, `superseded_by`.

### IDs
- One sequence per prefix. The next id is the highest existing number + 1, counting the archive. Never reuse or renumber.
- Existing ids (`V2-NN`, `TECH-V2-*`, `ADR-001…009`, `AUDIT-…`, `RESEARCH-…`, `HANDOFF-…`) are permanent. Code and migrations cite them, and cite TECH/ADR **section numbers** (`TECH-V2-ai-service §7.5`): append sections, never renumber.

### Filenames
Lowercase kebab-case, stable, with no volatile details (`adr-010-short-decision.md`, `test-report-003-upload-flow-2026-12-01.md`, `handoff-<scope>-YYYY-MM-DD.md`). One exception: V2 tickets keep `V2-NN-<slug>.md` (the id is the filename prefix; `eval/sopilot_eval/plan_check.py` globs `V2-*.md`).

### Links
Relative Markdown links in bodies, root-relative paths in `refs`. Link to the source of truth instead of copying it. `check-docs.ps1` fails on broken links.

### Lifecycle
- `approved`, `done` and `final` are owner decisions. Agents may propose them.
- A design states what is implemented and what is still planned. A documented design is not proof of implementation.
- A ticket is `done` only with evidence (tests or commands with results, linked in "Evidence") and owner review. `review` means the code is committed and evidence is pending review. `blocked` requires `blocked_reason`.
- Changing a ticket status updates the PLAN table and counters in the same edit (`completed` = done, `review` = review, `implemented` = done + review).
- An owner decision is recorded once, in the ADR or design it belongs to. The PLAN change log gets one dated line naming the affected tickets.
- ADR `amends` = partial change (the old ADR stays approved); `supersedes` = full replacement (the old one becomes superseded).
- Closing an initiative: set the README and PLAN to `archived`, move the folder to `archive/initiatives/`, and update links in the same change.

## Which document, if any

| Change | Write |
|---|---|
| Small bug fix | None (commit + test). Update a design only if it described the wrong behaviour |
| Endpoint / schema / RBAC change | Update the design section, the service README and `architecture/data` or `architecture/api` |
| Hard-to-reverse decision | ADR |
| Multi-ticket feature | Initiative (README + PLAN + tickets); design in `architecture/` if reusable |
| Risky or cross-service verification | Test plan, then a test report |
| Acceptance evidence | Test report |
| New operational procedure | Runbook in `operations/` |
| Investigation or experiment | Research |
| Stopping mid-task | Handoff |

Workflow: skill [`project-docs`](../.claude/skills/project-docs/SKILL.md). Validation: `./scripts/docs/check-docs.ps1` (strict) or `-Mode audit` (report-only, includes the archive).
