---
id: TICKET-NNN
title: "<scope>: <what changes>"
type: feat # commit type: feat | fix | chore | refactor | docs | test
status: todo # todo | in_progress | review | done | blocked
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: "Owner"
scope: core # core | ai | web | infra | eval | tenant | ci | plan
priority: P1 # P0 | P1 | P2 | P3
size: M # S | M | L (split anything larger)
parent_plan: PLAN-NNN
depends_on: []
blocks: []
blocked_reason: "" # required when status is blocked
branch: "<type>/<scope>-<short-name>"
refs: [] # design section / ADR this ticket implements
---

# TICKET-NNN: <Title>

## Context
Why now, and the design section it implements (link it; do not copy it).

## Acceptance criteria
- [ ] Binary, testable criterion.
- [ ] Tenant-scoped paths have a negative isolation case.

## Implementation notes
Likely files or modules and known traps. Not a step-by-step script.

## Verification
| Criterion | Command / test | Result |
|---|---|---|
| ... | `./scripts/run-tests.ps1 -Scope ... -Type unit` | filled in at review |

## Evidence
Test report link (`docs/quality/test-reports/...`) or commit ids. Required before `done`; `done` needs owner review.
