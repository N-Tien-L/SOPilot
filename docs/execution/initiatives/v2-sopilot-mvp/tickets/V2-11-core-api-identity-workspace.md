---
id: V2-11
title: "core-api: service skeleton, Google identity, JIT and personal workspace"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: user
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-08]
blocks: [V2-12, V2-15, V2-23, V2-29]
branch: "feat/user-core-api-identity"
assignee: pair
---

# TICKET V2-11: core-api (identity and workspace)

> Translated from Vietnamese on 2026-11-13; content unchanged. Context-doc paths under `.agent/context/` are as they were at the time; that content now lives in `docs/architecture/`.

## 1. Context & goal
The Spring Boot service `services/core-api` merges auth, user and the rest of metadata. Port `GoogleTokenVerifierService` and the `(issuer, sub)` binding from the M1 code; refresh-token rotation is ported in V2-29; add tenancy (ADR-005). Scope FR-01/FR-02; FR-03 moved to V2-29, FR-04/FR-05 to V2-30 (XL split on 2026-10-24, requirements unchanged).

## 2. Acceptance criteria
- [x] Google ID token verification (RS256/JWKS, `iss`, `aud`, `exp`, `email_verified`) **and a `nonce` check** (A9).
- [x] JIT users by `(issuer, sub)`; the personal workspace created automatically, idempotent (FR-02).
- [x] An initial JWT ≤ 15 minutes bound to the personal workspace and role; one service writes `users`/the initial membership. Workspace CRUD/switching and refresh moved to V2-29.
- [x] Dev login only in profiles `local`/`test`.
- [x] Errors returned to the client contain no internal `e.getMessage()` (A8); tokens/secrets are never logged.
- [x] Only one service writes `users`.
- [x] The token has room for the `wdept` claim (filled in V2-23); refresh and membership checks belong to V2-29.

## 3. Guide
- **Skeleton:** create `services/core-api/pom.xml`, the Maven wrapper, `src/main/java/com/sopilot/core/`, `src/main/resources/application.yml`, `src/test/`; add the `core`/`core-api` scopes to the build/test scripts and record the commands in the service README.
- **Files:** `services/core-api/` (CREATE); port sources: `services/auth-service/.../GoogleTokenVerifierService`, `AuthService`, `services/user-service`.
- Update `.agent/context/authorization/` and `service-boundaries/` in the same change; V2-17 consolidates them.
- Spring Boot/Java per the V2-01 decision.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | verifier (wrong signature, wrong aud, expired, wrong nonce), personal-workspace token | `./mvnw test` |
| Integration | Real Postgres: JIT idempotent/concurrent, owner membership, schema isolation | `./mvnw verify` |

Note: the Maven wrapper once failed (AUDIT 2026-10-14); confirm `./mvnw` runs first.

## 5. Implementation evidence (2026-11-04, accepted 2026-11-05)

The owner accepted on 2026-11-05 and set `done`. Code at commit `f25646b` on branch `feat/user-core-api-identity`. The "Not checked" items below were accepted as open: a real Google sign-in is checked with V2-15, applying the migration to the persistent DB happens when the V2 stack runs.

- **Code:** `services/core-api/` (Spring Boot 3.5.16, Java 21, Maven wrapper 3.9.12 working); migration `infrastructure/db/migrations/core/V003__identity_and_personal_workspace.sql` (`users`, `external_identities`, `workspaces`, `memberships`, RLS, `core.create_personal_workspace`).
- **Port:** `GoogleIdTokenVerifier` from V1's `GoogleTokenVerifierService` (V1 unchanged). Differences from V1: a `nonce` check against the HMAC-signed `sp_nonce` cookie, 60 s clock skew, a normalized issuer, errors always `401 INVALID_GOOGLE_TOKEN` (V1 returned `e.getMessage()` to the client), logs record only a reason code.
- **Unit (`./mvnw test`, 41 tests, green):** the verifier with a real RSA key and a local JWKS: wrong signature, HS256, `alg=none`, wrong `iss`, wrong `aud`, expired (outside/inside 60 s), a future `iat`, `email_verified=false`, wrong/missing nonce/missing cookie, missing `sub`/`email`, client id not configured; the nonce cookie (edited nonce, extended expiry, expired, another key); the personal-workspace token (`wid`, `wrole`, `wdept` always present, TTL 900 s, TTL > 15 minutes refused, no email/name); HTTP: dev login `404` in profile `prod`, `200` in `test`; 500 errors do not leak internal messages.
- **Integration (`./mvnw verify`, 14 tests, green, Testcontainers `pgvector/pgvector:0.8.0-pg16` + the real `01-roles.sh` + the full core Flyway chain, rag up to V002, connected as `sopilot_core_app`):** repeated dev login gives the same user/workspace; 8 concurrent first sign-ins → 1 user, 1 identity, 1 workspace, 1 OWNER membership; the same email with another issuer → 2 users; the token verifies through `/.well-known/jwks.json`; no tenant set → 0 rows; a user sees only their own workspaces; no reading/writing other workspaces (RLS `WITH CHECK`); a pooled connection (pool = 1) does not carry the tenant into the next transaction, even after a rollback; `sopilot_core_app` has no rights on `rag`, no `CREATE` in `core`, cannot disable RLS; `create_personal_workspace` is SECURITY DEFINER, not granted to `sopilot_ai_app`/PUBLIC, idempotent.
- **Scripts:** `./scripts/validate-build.ps1 -Scope core` and `./scripts/run-tests.ps1 -Scope core-api -Type all` green; `check-conventions.ps1 -Scope core` maps to `services\core-api`.
- **Not checked:** a real Google sign-in in the browser (needs `GOOGLE_CLIENT_ID` and the V2-15 frontend); running V003 with compose's Flyway 10.20.1 container (the tests use Flyway 11 from Spring Boot); not applied to the owner's persistent DB.
- **Deviations from TECH:** `core.create_personal_workspace` takes an extra `p_workspace_id` (a UUIDv7 generated by the app, TECH §3); no default `local` profile (TECH §9 says `local` by default), so missing configuration stops the service instead of enabling dev login; JWKS publishes only the current key, not yet the previous one (rotation, needed with several keys). The owner approved all three (2026-11-05); TECH updated in §4.2, §5.1, §9, and the previous JWKS key moved to V2-29.
- **Docs:** `.agent/context/authorization/v2-core-identity.md` (new), `database/schema.md`, `database/tables/core.md`, `service-boundaries/responsibilities.md`, `service-boundaries/api-contracts.md`, `.agent/context/README.md`, `.env.example`, `services/core-api/README.md`.
