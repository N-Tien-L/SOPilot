---
id: V2-29
title: "core-api: workspace CRUD, workspace switching and refresh sessions"
type: feat
status: done
created: 2026-10-24
updated: 2026-11-13
author: "Owner"
scope: user
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-11]
blocks: [V2-15, V2-30]
branch: "feat/user-v2-29"
assignee: pair
---

# TICKET V2-29: core-api: workspace CRUD, workspace switching and session refresh

> Translated from Vietnamese on 2026-11-13; content unchanged. Context-doc paths under the former agent context folder are as they were at the time.

## 1. Context & goal
Splits the FR-03 part out of V2-11 (XL). Follows TECH-V2-core-api §3.1–§3.2, §4, §5.1–§5.2; does not change the approved contract.

## 2. Acceptance criteria
- [x] Workspace CRUD, listing and switching by membership; no access to another workspace by ID alone. (create TEAM, list, `/current` read/rename/soft delete; switching returns `404` when not a member; administration always uses the token's `wid`. **Hard deletion** of the workspace row after ai-service confirms is not done, see TECH §14)
- [x] Token ≤ 15 minutes bound to `workspace_id`, role and room for `wdept`; refresh checks the membership status and takes the current values.
- [x] Rotating refresh tokens, replay detection and session revocation per TECH; tokens are not logged, errors do not reveal internals. (plus the `Origin` check, revocation on suspension/removal/leaving)
- [x] The RLS context is set inside the transaction; a connection returned to the pool does not keep the old tenant. (`TenantTx` as in V2-12; `TenantIsolationIT` uses a 1-connection pool)
- [x] JWKS publishes the current and previous keys (TECH §5.1) so rotating the signing key does not drop sessions; V2-11 had only the current key. (`SOPILOT_JWT_PREVIOUS_PUBLIC_KEY_PATH`; the verifier picks the key by `kid`)
- [x] V2-30's invitations/OWNER policy reuse this workspace/session service without duplicating logic. (only checkable during V2-30; moved to a V2-30 criterion. Reuse points: `WorkspaceSessionService.switchTo`, `RefreshTokenService.revokeForMembership`)

## 3. Guide
1. Port refresh rotation from `services/auth-service` into `services/core-api/src/main/java/com/sopilot/core/identity/`.
2. Add the workspace controller/service/repository in `services/core-api/src/main/java/com/sopilot/core/workspace/`.
3. Add the next migration in `infrastructure/db/migrations/core/` for sessions/workspaces if not part of V2-11; do not edit migrations that have run.
4. Add tests in `services/core-api/src/test/`, update the README and the API contract.
- Update the related contracts in the former agent context (now `docs/architecture/`) along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Unit: wrong/expired token, workspace without membership, revoked session.
- Postgres integration: refresh replay, workspace switching, rollback and reuse of a connection across tenants.
- Commands: `./scripts/run-tests.ps1 -Scope core-api -Type all`, `./scripts/validate-build.ps1 -Scope core` (scope built by V2-11), pre-commit.

## 5. Implementation evidence (2026-11-08, accepted 2026-11-09)

Owner acceptance 2026-11-09, moved to `done`. Code in commits `6ec8dde`, `622359e`, merged into `develop` (`e127c07`). The deviations from TECH in TECH-V2-core-api §14 are approved; the owner settled that **hard deletion of the workspace row** is outside the MVP (local run; soft deletion already blocks access and refresh), no ticket added. Rechecked at acceptance: `./mvnw -B verify` on `develop` (`c71138b`) → 78 unit + 101 integration, 0 failures (`SessionWorkspaceIT` 23); GitHub Actions on `develop` green (`Poliwise CI` run 42506269350, `Tenant isolation (FR-19)` run 42506269294, 2026-11-08). Reread `RefreshTokenService`, `WorkspaceSessionService`, `WorkspaceService`, `V006`: tokens are stored only as SHA-256, the row is locked on rotation, reusing an old token revokes the whole family and the revocation is committed (returning a refusal instead of throwing), membership is reread on every refresh and deleted workspaces are skipped.

- **Review notes (non-blocking):** (1) strict rotation: two tabs sending the same refresh cookie almost simultaneously make the second one count as reuse, and the whole session is logged out; the frontend (V2-15) must merge concurrent refreshes into one. (2) `RefreshTokenService.revokeForWorkspace` is currently not called (workspace deletion relies on `findMembership` per TECH §14).

- **Code:** `services/core-api/src/main/java/com/sopilot/core/identity/` (`RefreshTokenService`, `RefreshTokenRepository`, `WorkspaceSessionService`, `WorkspaceSessionController`, `AuthController`), `workspace/` (`WorkspaceService`, `WorkspaceController`), `security/` (`SigningKeyProvider`, `AccessTokenVerifier`, `WorkspaceRole`); migration `V006__refresh_tokens_and_workspace_soft_delete.sql`.
- **Commands:** `./mvnw verify` in `services/core-api` → 78 unit + 101 integration, 0 failures (new: `SessionWorkspaceIT` 23 tests on real Postgres, `SigningKeyRotationTest` 5 tests). `tests/tenant-isolation` → 31 passed. `./scripts/check-migrations.ps1` → pass.
- **Coverage:** rotation and the new token in the same family; reusing an old token revokes the whole chain (including the successor token); unknown/expired token; role reread from the DB; suspension (`403 MEMBERSHIP_SUSPENDED`) and lost membership (`401 MEMBERSHIP_LOST`); suspension/removal through the API revokes the chain immediately; wrong/missing `Origin` → `403`; cookie `HttpOnly; SameSite=Strict; Path=/api/v1/auth`; logout always `204`; workspace switching (member, non-member `404`, suspended `403`, missing bearer `401`); workspace creation (name check, OWNER, new token); only the OWNER renames/deletes; a personal workspace cannot be deleted; deleting a workspace emits one `DOCUMENT_DELETED` per document and blocks refresh; tokens signed with the previous key are still accepted, an unknown key or a forged `kid` is refused.
- **Deviations/notes:** see TECH-V2-core-api §14. Notably: the column `refresh_tokens.target_workspace_id` (not `workspace_id`) so the isolation suite does not treat the global table as a tenant table; `WorkspaceRole` moved to `security`; workspace creation/switching lives in `identity` so `ArchitectureTest` does not report a cycle.
- **Not done:** hard deletion of the workspace row (outside the MVP, owner settled 2026-11-09); domain join (FR-05, P1, a V2-30 criterion); confirming V2-30 reuses this service (a V2-30 criterion); the two real services have not run together. ~~No GitHub Actions run yet~~: green on `develop` 2026-11-08.
- **Docs:** `services/core-api/README.md`, the former agent context `authorization/v2-core-identity.md`, the former agent context `database/tables/core.md`, `.env.example`, TECH-V2-core-api §14, PLAN-V2.
