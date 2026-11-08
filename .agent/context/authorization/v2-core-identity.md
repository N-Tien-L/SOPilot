# V2 core-api identity and tenancy (V2-11, 2026-11-04)

Read before changing V2 login, access tokens, JIT provisioning or RLS in `services/core-api`.
Source of truth: [TECH-V2-core-api](../../../docs/02-architecture/designs/TECH-V2-core-api.md) §3.1–§5.1, ADR-005.
The V1 notes in `google-admission.md` (roster admission, auth-service) do not apply to V2.

- **Identity** is `(issuer, subject)` in `core.external_identities`; email is an attribute, not unique.
  Google issuers `accounts.google.com` and `https://accounts.google.com` are stored as the canonical
  `https://accounts.google.com`. Dev login uses issuer `sopilot-dev`, subject = lower-case email.
- **Google verification** (`identity/GoogleIdTokenVerifier`, ported from V1 `GoogleTokenVerifierService`):
  RS256 via Google JWKS only, `iss`, `aud = GOOGLE_CLIENT_ID`, `exp`/`iat`/`nbf` with 60 s skew,
  `email_verified = true`, `nonce` equal to the nonce inside a valid `sp_nonce` cookie
  (`<nonce>.<exp>.<HMAC-SHA256>`, 5 min, not stored). Every failure is `401 INVALID_GOOGLE_TOKEN`;
  the reason is logged as a code only. The cookie is cleared after every login attempt.
- **No roster gate** (TECH §11 Q5): any verified Google account gets a user and a PERSONAL workspace.
- **JIT** (`identity/IdentityService`): one transaction, `pg_advisory_xact_lock` on issuer+subject,
  insert user + identity if absent, then `core.create_personal_workspace(user, newId, name, email)`
  (SECURITY DEFINER, idempotent through `uq_personal_workspace`) creates the workspace and the
  OWNER/ACTIVE membership. Concurrent first logins yield one user, one workspace, one membership.
- **Access token** (`security/AccessTokenIssuer`): RS256, `kid`, `iss=sopilot-core`,
  `aud=[sopilot-core, sopilot-ai]`, `sub`, `wid`, `wrole`, `wdept` (always present, null until V2-23),
  `jti`, `iat`, `exp`; TTL ≤ 15 min enforced at startup. No email/name. Public key at
  `/.well-known/jwks.json` (current key, plus the previous public key during a rotation, V2-29).
- **Dev login** exists only with profile `local` or `test` (`@Profile`); otherwise the route is 404.
  Without those profiles the service also refuses to start without a signing key and nonce key.
- **RLS**: `core.workspaces` and `core.memberships` are `FORCE ROW LEVEL SECURITY`. `RlsContext.bind`
  sets `app.workspace_id`/`app.user_id` with `set_config(..., true)` inside a transaction. Unset means
  no rows. Policies `definer_access` (role `sopilot_migrator`) exist only so SECURITY DEFINER helpers
  work under FORCE RLS; `sopilot_core_app` is unaffected.
- **Per-request auth (V2-12/V2-23):** `security/JwtAuthFilter` verifies the bearer token (`AccessTokenVerifier`:
  RS256 signature, `iss`, `aud` contains `sopilot-core`, `exp`, claim shape) on every `/api/v1/**` except
  `/api/v1/auth/**`; controllers take an `AuthPrincipal` (`sub`, `wid`, `wrole`, `wdept`). `tenancy/TenantTx` binds
  `app.workspace_id`/`app.user_id` from that principal at the start of each transaction (an explicit wrapper,
  not a transaction listener as TECH section 4.3 sketches). `role` and `wdept` are read from the token, so a change
  takes effect at the next token issue (<= 15 min, ADR-007 section 4.5). `/internal/**` is guarded by
  `InternalTokenFilter` (`X-Internal-Token`, constant-time compare, blank token = reject all).
- **Roles:** OWNER/ADMIN upload, replace, retry, edit and delete documents, manage departments and members, and
  read version history; every member lists, reads and downloads (`download-url`, <= 300 s). OWNER only: audit log.
  An ADMIN cannot suspend or remove an OWNER; the workspace always keeps one ACTIVE OWNER (`LAST_OWNER`, checked
  under a row lock on the owners). A PERSONAL workspace cannot be left.
- **Re-issue:** `identity/SessionTokenService.reissue(user, workspace)` re-reads the membership: removed ->
  `401 MEMBERSHIP_LOST`, `SUSPENDED` -> `403 MEMBERSHIP_SUSPENDED`, else a token with current role and `wdept`.
- **Refresh (V2-29, `identity/RefreshTokenService`):** 256-bit token in the `sp_refresh` cookie (HttpOnly,
  SameSite=Strict, path `/api/v1/auth`, 14 days); only its SHA-256 is stored in `core.refresh_tokens` (global, no
  RLS). Each use exchanges it for the next token of the same family under a row lock; a token that was already
  exchanged or revoked revokes the whole family. The membership is re-read on every refresh (removed ->
  `401 MEMBERSHIP_LOST`, suspended -> `403 MEMBERSHIP_SUSPENDED`, chain revoked), and the new access token carries
  `wrole`/`wdept` from the database. `/auth/refresh` and `/auth/logout` also require `Origin` =
  `SOPILOT_FRONTEND_ORIGIN`. Suspend, remove and leave revoke the member's chains for that workspace.
- **Workspaces (V2-29):** `workspace/WorkspaceService` (list, current, rename, soft delete) and
  `identity/WorkspaceSessionService` (create TEAM, switch; they issue tokens, so they sit in `identity` to keep
  `ArchitectureTest` cycle-free). `/current` endpoints use the token's `wid`. Delete is soft: `workspaces.deleted_at`,
  one `DOCUMENT_DELETED` outbox event per document; a deleted workspace has no usable membership, so refresh
  ends with `MEMBERSHIP_LOST` (access tokens already issued live <= 15 min). The row is not purged yet.
- `WorkspaceRole` lives in `security` (moved from `WorkspaceRepository`) so `workspace` can use `AuthPrincipal`.
- Not yet: invitation endpoints and acceptance, role changes, `pendingInvitations` (V2-30; returned as `[]`),
  workspace domains (FR-05, P1).
