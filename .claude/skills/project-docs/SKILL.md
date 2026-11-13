---
name: project-docs
description: Create, update or audit SOPilot documentation in docs/ (PRD, ADR, design, initiative/PLAN/tickets, test plan/report, runbook, research, handoff) in English with the repo's frontmatter, id and status rules. Use when asked to draft requirements, record a decision, design, plan or split tickets, write evidence or a handoff, reconcile docs with code after a change, or find where something is documented. Not for code changes.
---

# Project documentation

Conventions (kinds, ids, statuses, filenames, lifecycle) are in `docs/README.md` → "Conventions". Read that section; do not redefine it here.

## 1. Decide whether a document is needed
Use the "Which document, if any" table in `docs/README.md`. Prefer updating the existing source of truth over creating a new file. A small fix usually needs no document.

## 2. Find the source of truth (discovery)
1. Start from the `docs/README.md` map and the `CLAUDE.md` "Finding knowledge" table. Open only the files the task needs.
2. Search by id before searching by words: `rg -n "TECH-V2-core-api §5|FR-19|V2-24" docs services`.
3. Confirm against code and config (`git grep`, migrations, `config/models.yaml`, the service README endpoint tables). Code wins. Record any mismatch in your report; if it matters, add it to the doc as **Unverified / mismatch** instead of guessing.

## 3. Create or update
- Copy the template from `docs/templates/`. Fill only the sections that carry information; delete the rest.
- New id: the highest existing number for that prefix + 1, counting `docs/archive/`. Filenames are lowercase kebab-case (V2 tickets keep `V2-NN-…`).
- Never renumber TECH/ADR sections. Append new ones.
- Owner decisions: write them once in the ADR or design; add one dated change-log line to the PLAN naming the affected tickets.
- Ticket status change → update the PLAN table and the counters in the same edit; keep `depends_on` ↔ `blocks` ↔ the Mermaid DAG consistent (both `check-docs.ps1` and `eval/sopilot_eval/plan_check.py` check this).
- Mark planned behaviour as planned. Do not set `approved`, `done` or `final` yourself; propose it to the owner.

## 4. Handoff (stopping mid-task)
Write `docs/handoffs/handoff-<scope>-YYYY-MM-DD.md` from the template: goal, state (branch, last commit, implemented vs planned, uncommitted files), owner decisions, files to read, next steps, verification commands. When the work is finished, move the handoff to `docs/archive/handoffs/`.

## 5. Audit
`./scripts/docs/check-docs.ps1 -Mode audit` lists legacy issues (including the archive) without failing. Report findings grouped by severity; fix only what the task covers.

## Verify before finishing
- `./scripts/docs/check-docs.ps1` prints `docs check passed`.
- For PLAN/ticket edits, also run `cd eval; uv run pytest -q tests/test_review_regressions.py -k plan`.
- Every new link resolves.

## Done when
The document follows its template and conventions, the validators pass, and the report to the user lists the documents changed, the code/doc mismatches found, and the decisions still needed from the owner.

## Never
Name an AI as author; translate identifiers, commands or quoted sources; edit `docs/archive/` content; copy code, schemas or endpoint tables into docs when a link will do.
