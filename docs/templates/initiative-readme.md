---
title: "<Initiative name>"
status: approved # draft | approved | superseded | archived
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: "Owner"
plan: PLAN-NNN
refs: [] # PRD, ADRs, designs (root-relative)
---

# <Initiative name>

**Goal:** one sentence. **Progress:** the status table in [PLAN.md](PLAN.md) (do not repeat it here).

| Read | For |
|---|---|
| PRD link | What and why |
| Design links | How (shared architecture docs) |
| [PLAN.md](PLAN.md) | Order, dependencies, status |
| [tickets/](tickets/) | Units of work |
| `designs/` (optional) | Initiative-only design notes that are not reusable architecture |

## Closing
When every ticket is `done` (or the plan is `superseded`), set `status: archived` here and on PLAN.md, and move the folder to `docs/archive/initiatives/` in the same change as the link updates.
