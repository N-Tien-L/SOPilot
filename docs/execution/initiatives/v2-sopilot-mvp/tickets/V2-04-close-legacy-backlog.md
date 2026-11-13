---
id: V2-04
title: "Close the M1/NEXT backlog and clean up duplicate documents"
type: docs
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: docs
priority: P1
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-01]
blocks: [V2-18]
branch: "docs/docs-close-legacy"
assignee: pair
---

# TICKET V2-04: Close the old backlog

> Translated from Vietnamese on 2026-11-13; content unchanged. Paths are given as they were at the time (`docs/03-plans/`, `docs/_archive/`); those folders are now `docs/execution/` and `docs/archive/`.

## 1. Context & goal
Avoid confusing progress between the two directions. Done only after V2-01 is approved.

## 2. Acceptance criteria
- [x] NEXT-01, 03, 04, 05, 06 move to a closed status. Frontmatter gained `superseded` per `docs/README.md`; the body names the replacing document. Choose one approach and state it.
  - **Chosen:** add `superseded` to the ticket status table in `docs/README.md` (not counted in the PLAN counters); each ticket names its replacing ticket/document at the top of its body. M1-06 (M1's E2E, outside the original list) is also `superseded`, mapped to V2-14/V2-26/V2-17.
- [x] NEXT-02, M1-03, M1-04, M1-05: keep their `review`/`in-progress` status, with a note "ported to V2-11".
- [x] PLAN-M1 and PLAN-NEXT (`status: superseded`) note that PLAN-V2 replaces them.
- [x] Delete `docs/plans/` (deprecated) only once NEXT-02 is committed (commit `9638f0a`); all 14 files were tracked, with no uncommitted changes; remove mentions of `docs/plans/` from `AGENTS.md`, `CLAUDE.md`, `docs/README.md` and the `execute-ticket` skill; check `git status` first and delete nothing outside the exact path.
- [x] Finish the `fix/auth-google-roster-admission` branch and PR through `develop`: done before this ticket (PR #2 merged into `origin/develop`, commit `2954aca`).

## 3. Guide
- **Files:** `docs/_archive/03-plans/PLAN-M1-jit-onboarding.md`, `PLAN-NEXT-implementation-readiness.md`, the tickets above, `docs/README.md`.
- **Action:** MODIFY. Keep the PLAN counters consistent with the ticket frontmatter.

## 4. Testing
Compare the PLAN counters with the frontmatter using `Grep "status:"` on `docs/03-plans/tickets/` (which then also held the M1/NEXT tickets).

Result 2026-10-20: `Grep "status:"` on `docs/03-plans/tickets/` matches the counters: PLAN-M1 2 done, 2 review (implemented 4); PLAN-NEXT 0 done, 1 review (implemented 1). `superseded` is not counted. The document review was completed by Codex on 2026-10-24; see the evidence below.

### Review 2026-10-24
Checked the status/replacing document of the 12 M1/NEXT tickets and the counters of both PLANs, confirmed that `docs/plans/` no longer exists and that commits `9638f0a`, `2954aca` are in HEAD's history. Fixed the stale starting instructions and folder tree in `docs/README.md`. The historical M1/NEXT statuses were not changed and no further files were deleted. Evidence: [AUDIT readiness](../../../../archive/reports/AUDIT-v2-readiness-preparation-2026-10-24.md).
