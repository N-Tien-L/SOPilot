---
id: V2-30
title: "core-api: invitations, members and OWNER rules"
type: feat
status: done
created: 2026-10-24
updated: 2026-11-13
author: "Owner"
scope: user
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-29]
blocks: [V2-15, V2-33]
branch: "feat/user-v2-30"
assignee: pair
---

# TICKET V2-30: core-api: invitations, members and OWNER rules

> Translated from Vietnamese on 2026-11-13; content unchanged. Context-doc paths under `.agent/context/` are as they were at the time.

## 1. Context & goal
Splits FR-04 and the P1 part of FR-05 out of V2-11. Follows TECH-V2-core-api §3.2, §5.3 and ADR-005.

## 2. Acceptance criteria
- [x] Invitations: single-use link, valid 7 days, revocable; a mismatched email or an expired invitation is refused.
- [x] Accepting an invitation creates the membership idempotently; two concurrent requests neither create duplicates nor reuse the link.
- [x] (Moved from V2-29) Accepting invitations and OWNER operations reuse `WorkspaceSessionService.switchTo` (issuing a token for the new workspace) and `RefreshTokenService.revokeForMembership` (revoking sessions on role change/removal), without duplicating session logic.
- [x] At least 1 OWNER always remains; an ADMIN cannot promote or remove an OWNER; cross-workspace operations are refused.
- [ ] (P1, may be deferred with a record) Domain join through the `hd` claim (FR-05). **Deferred (2026-11-11):** not done; recorded in TECH-V2-core-api §16.
- [x] No automatic email unless the owner allows it; the invitation-link API still works.
- [x] (Moved from V2-23) Invitations carry a profile (`display_name`, `employee_code`, `job_title`, `department_id`; the `core.invitations` table exists since `V004`) applied to the membership on acceptance; no invitations into `ARCHIVED` departments; a duplicate `employee_code` in the workspace is refused. Integration: invite with a profile → accept → the token carries `wdept`.
- [ ] (P1, may be deferred with a record; moved from V2-23, FR-24) CSV import creating invitations in bulk, with per-row errors. **Deferred (2026-11-11):** not done; recorded in TECH-V2-core-api §16.

## 3. Guide
1. Add the controller/service in `services/core-api/src/main/java/com/sopilot/core/member/`.
2. Add the next additive migration in `infrastructure/db/migrations/core/` for invitations/constraints if needed.
3. Add to `services/core-api/src/test/` for transactions and OWNER invariants; update the API docs.
- Update the related contracts in `.agent/context/` along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Unit: last OWNER, ADMIN promoting to OWNER, mismatched email, expired/revoked invitation.
- Integration: accepting a link twice/concurrently, two OWNERs leaving at once, workspace isolation.
- Commands: `./scripts/run-tests.ps1 -Scope core-api -Type all`, `./scripts/validate-build.ps1 -Scope core`, pre-commit.

## 5. Implementation notes and evidence (2026-11-11)

- Migration `core/V008__invitation_acceptance.sql` (`SECURITY DEFINER` functions `accept_invitation`, `pending_invitations_for_user`); V2-36 moved to `V009`.
- Code: `member/InvitationController|Service|Repository`, `MemberService` (roles, OWNER rules, the caller's role read from the DB), `pendingInvitations` in `IdentityService`.
- Deviations from TECH recorded in TECH-V2-core-api §16 (the same person accepting the link again gets `200`, a role change revokes sessions with `MEMBERSHIP_LOST`, FR-05 and FR-24 deferred).
- Tests: `InvitationServiceTest` (unit), `InvitationIT`, `OwnerPolicyIT` (including concurrent acceptance, two OWNERs leaving at once, a demoted OWNER still holding the old token, workspace isolation). `./scripts/run-tests.ps1 -Scope core-api -Type all` green; `check-migrations.ps1` green; `tests/tenant-isolation` 31 passed.
- Not checked: no email sending (out of scope), no UI yet (V2-15/V2-33).
