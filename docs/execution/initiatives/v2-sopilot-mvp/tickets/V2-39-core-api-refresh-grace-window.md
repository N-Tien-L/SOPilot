---
id: V2-39
title: "core-api: refresh-token grace window so a reload during a refresh does not end the session"
type: fix
status: todo
created: 2026-11-15
updated: 2026-11-15
author: "Owner"
scope: user
priority: P1
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-29]
blocks: [V2-18]
branch: "fix/user-refresh-grace-window"
assignee: pair
refs:
  - docs/architecture/components/core-api.md
  - docs/architecture/domain/identity-and-access.md
  - docs/architecture/components/frontend-nfrs.md
---

# TICKET V2-39: Refresh-token grace window

> **Scope:** `user` | **Size:** `S` | **Priority:** `P1`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `fix/user-refresh-grace-window`

## 1. Context & goal
Found by the V2-38 browser run (2026-11-15, [V2-38 Results](V2-38-frontend-foundation.md), finding 1). `POST /auth/refresh` rotates the token under a row lock ([TECH-V2-core-api §5.1](../../../../architecture/components/core-api.md), `RefreshTokenService.rotate`): a token that was already exchanged revokes the whole family. If a tab is reloaded while its refresh request is in flight, the server has already rotated the token but the aborted response's `Set-Cookie` never reaches the browser. The next refresh presents the used token, which counts as reuse, and the user is signed out. In a Chromium test a double reload 5 ms apart lost the session on trial 2 of 12. The frontend cannot prevent it: only the server knows the rotation happened. Cross-tab merging (V2-38, C5/R1) is not affected and works.

Goal: tolerate this one benign race without weakening replay detection. The owner approved the approach on 2026-11-15 (accept the immediately previous token for a few seconds); the exact mechanism is part of this ticket and needs the design update below.

## 2. Acceptance criteria
- [ ] **Grace.** A refresh token that was exchanged less than a short, configurable time ago (default 10 s, `SOPILOT_REFRESH_GRACE`; `0` turns it off) and whose successor has **not** been presented yet is accepted once more and answered with a new session, instead of triggering `REUSE_DETECTED`. The cookie in that response is the token the browser must use from then on.
- [ ] **Replay stays detected.** A used token presented after the window, or presented again inside it after the successor was used, still revokes the whole family (`REUSE_DETECTED`). The refresh token value is never logged.
- [ ] **No fork.** After a grace refresh exactly one live token exists per family (the earlier successor is retired), so two browsers cannot each hold a valid chain.
- [ ] **Race test.** An integration test sends two refresh requests with the same cookie value in quick succession (and one after the window) and asserts: first accepted, second accepted inside the window and returns a usable session, a replay after the window revokes the family, and the membership checks (`MEMBERSHIP_LOST`, `MEMBERSHIP_SUSPENDED`) still apply on the grace path.
- [ ] **Design and docs.** [TECH-V2-core-api §5.1](../../../../architecture/components/core-api.md) step 2 and [identity and access](../../../../architecture/domain/identity-and-access.md) describe the window (append, never renumber sections); `services/core-api/README.md` lists the new variable; `services/core-api/.env.example` documents it with a dummy value.
- [ ] **Browser re-check.** Repeat the V2-38 double-reload trial (Chromium and Firefox, 12 trials) and record that the session survives.

## 3. Guide
- Code: `identity/RefreshTokenService.rotate`, `RefreshTokenRepository` (the row already stores `used`; it needs the time it was used and a pointer to its successor, so a migration in the `core` chain is likely: skill `flyway-migration`; additive only).
- The window must be short, apply only to the immediately previous token, and only while its successor is unused. Do not extend `refreshTtl` or relax the `Origin` check.
- Security note for review: the grace path lets a stolen just-rotated token be used once inside the window. The family-wide revocation on any later reuse limits it; record this trade-off in the design update.
- Not in this ticket: frontend changes (none needed), changing access-token lifetime, device or session management.

## 4. Testing
```powershell
./scripts/run-tests.ps1 -Scope core-api -Type unit
./scripts/run-tests.ps1 -Scope core-api -Type all   # Docker
./scripts/check-migrations.ps1
```
Plus `tests/tenant-isolation` if the migration touches RLS tables (refresh tokens are global, no RLS).

## 5. Changed files
| Area | Action |
|---|---|
| `services/core-api/.../identity/RefreshTokenService.java`, `RefreshTokenRepository.java`, config properties | MODIFY |
| `infrastructure/db/migrations/core/V0NN__refresh_token_grace.sql` | CREATE (if columns are needed) |
| core-api tests (unit and integration) | CREATE / MODIFY |
| TECH-V2-core-api §5.1, `identity-and-access.md`, `services/core-api/README.md`, `.env.example` | MODIFY |

## 6. Results
*(Fill in when running: commit, command results, browser notes.)*
