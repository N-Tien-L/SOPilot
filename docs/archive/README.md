# Archive

Historical documents kept for traceability. Nothing here is a current specification, and agents should not load it as context unless a task is about history (for example porting V1 behaviour before V2-17).

Files are kept as they were when archived: original language (often Vietnamese), frontmatter and status. Only links broken by later moves are fixed. `./scripts/docs/check-docs.ps1` checks this folder for broken links and duplicate ids only.

| Folder | Contents |
|---|---|
| `01-requirements/`, `02-architecture/`, `03-plans/`, `04-reports/` | The closed V1 document chains (M1 JIT onboarding, NEXT readiness backlog) and their reports, archived by V2-04 |
| `reports/` | Point-in-time reports that are no longer current: the V2 readiness preparation check (2026-10-24) and the slide-workflow research (2026-10-21) |
| `handoffs/` | Handoffs whose work is finished: the research workstreams kickoff (2026-10-18) and the V2-10 Q&A pipeline handoff (2026-11-08) |
| `v1-context/` | Snapshot of the V1 agent context (`.agent/context/`) taken on 2026-11-13, unmodified. It describes the frozen eight-service V1 stack; the V2 parts were merged into `docs/architecture/` (system overview, components/frontend, domain/identity-and-access, data/core-schema, data/rag-schema, api/http-conventions) |
