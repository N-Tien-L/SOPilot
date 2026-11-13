---
id: V2-23
title: "core-api: member profiles, suspension lifecycle and flat departments"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: user
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-11]
blocks: [V2-24, V2-26, V2-33, V2-36]
branch: "feat/user-core-api-members-departments"
assignee: pair
---

# TICKET V2-23: Member profiles and departments

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
PRD-V2 FR-04 (the profile part of invitations), FR-22, FR-23, FR-24 (P1), FR-20 (the staff part); ADR-007 §4.1–4.3. The profile lives on the membership and the invitation is the pending state; no pre-created roster.

## 2. Acceptance criteria
- [x] Memberships have `display_name`, `employee_code` (optional, unique in the workspace), `job_title` (optional), `department_id` (nullable), `status` `ACTIVE | SUSPENDED`; invitations carry these fields and apply them on acceptance. (The profile columns exist and are tested; the `invitations` table carries the profile fields; the invite/accept endpoints and applying the profile on acceptance moved to V2-30)
- [x] Suspend/unsuspend members: refresh issues no token for a suspended workspace; an ADMIN cannot suspend an OWNER; ≥ 1 `ACTIVE` OWNER always remains. (OWNER rules, suspension, unsuspension done; `SessionTokenService.reissue` returns `403 MEMBERSHIP_SUSPENDED`; the refresh endpoint and revoking refresh tokens on suspension/removal/leaving were done in V2-29, with `MemberService` calling `RefreshTokenService.revokeForMembership`)
- [x] Leaving/removal from a workspace does not delete the global account; personal workspaces require no profile or department.
- [x] Flat per-workspace departments: create, rename, `ARCHIVED`; names unique within the workspace; no new assignments to an `ARCHIVED` department.
- [x] Deleting a department is refused (409) while it has members, pending invitations or referencing documents (FK `RESTRICT`). (Pending invitations are blocked by a service check; the `invitations` FK is `SET NULL` instead of `RESTRICT` so used/revoked invitations do not pin a department)
- [x] The access token has a `wdept` claim; refresh re-reads `status` and `department_id` (ADR-007 §4.5). (Reissued tokens read `status`/`department_id` from the DB; no refresh endpoint yet, V2-29)
- [x] Audit: department changes, suspension/unsuspension, profile edits.
- [x] (P1, may be deferred) CSV import creating invitations in bulk, with errors per row (FR-24). (Deferred by the owner on 2026-11-09, moved to V2-30 as a P1 criterion)

## 3. Guide
- **Files:** the members/departments modules in `services/core-api/`; migrations in `infrastructure/db/migrations/`.
- For reference, not a straight port: `services/user-service` (`DepartmentService`, `EmployeeRoster*`), `frontend/web/app/admin/departments/`.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | Membership lifecycle; OWNER rules; archived departments; blocked deletion | `./mvnw test` |
| Integration | Invitation with a profile → acceptance → token with `wdept`; suspension → refresh refused; department move → the new token changes `wdept` | `./mvnw verify` |

## 5. Implementation evidence (2026-11-06, accepted 2026-11-09)

The owner accepted on 2026-11-09 and set `done`. Code at commit `4113f63`, merged into `develop` through PR #5. The parts depending on endpoints that did not exist yet were done in V2-29 (refresh, token revocation on suspension) or became criteria of V2-30 (invitations with profiles, P1 CSV import). The TECH deviations (FK `invitations.department_id` `SET NULL`, `PATCH /members` not yet accepting `role`) were approved in TECH-V2-core-api §13. Recheck at acceptance: `DepartmentMemberIT` 12 green in `./mvnw -B verify` (73 unit + 78 integration, 0 failures); reread `MemberService`, `MemberRepository`, `DepartmentService`, `DepartmentRepository`: every statement filters `workspace_id`, and the last-OWNER check locks the OWNER rows before changing them.

- **Code:** `services/core-api/src/main/java/com/sopilot/core/{department,member}/`, `identity/SessionTokenService.java`; migration `V004__departments_and_member_profiles.sql` (`departments`, `memberships.employee_code/job_title` + a two-column FK, `invitations`).
- **Commands:** `./mvnw verify` → 0 failures; V2-23 alone: `DepartmentMemberIT` 12 tests on real Postgres with role `sopilot_core_app`: department names unique per workspace (case-insensitive; the same name in another workspace is allowed); archiving departments; deletion gets `409 DEPARTMENT_IN_USE` while there are members, pending invitations or documents (the FK `RESTRICT` checked separately), revoked invitations do not pin; no assignment to an archived department; `employee_code` unique; a department move → the reissued token carries the new `wdept`, the token in hand keeps the old value; suspension → `403 MEMBERSHIP_SUSPENDED`, unsuspension → reissue works; removal from the workspace → `401 MEMBERSHIP_LOST`, the global account remains; an ADMIN cannot suspend/remove an OWNER; the last OWNER cannot suspend/remove/leave themselves (`LAST_OWNER`); a personal workspace cannot be left and requires no profile; a MEMBER sees only their own profile; audit `MEMBER_DEPARTMENT_CHANGED`, `MEMBER_PROFILE_UPDATED`, `MEMBER_SUSPENDED`.
- **Deviations/notes:** `PATCH /members/{userId}` does not accept `role` yet (role changes and the full OWNER rules are V2-30); the `PATCH` body is a map, so an explicit `null` clears an optional field.
- **Not done:** CSV import (P1); accepting invitations with profiles; revoking refresh tokens on suspension; frontend (V2-33).
- **Docs:** as V2-12.
