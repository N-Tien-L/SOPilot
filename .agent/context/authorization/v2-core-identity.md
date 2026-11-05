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
  `/.well-known/jwks.json`. No refresh token yet (V2-29).
- **Dev login** exists only with profile `local` or `test` (`@Profile`); otherwise the route is 404.
  Without those profiles the service also refuses to start without a signing key and nonce key.
- **RLS**: `core.workspaces` and `core.memberships` are `FORCE ROW LEVEL SECURITY`. `RlsContext.bind`
  sets `app.workspace_id`/`app.user_id` with `set_config(..., true)` inside a transaction. Unset means
  no rows. Policies `definer_access` (role `sopilot_migrator`) exist only so SECURITY DEFINER helpers
  work under FORCE RLS; `sopilot_core_app` is unaffected.
- Not yet: membership checks per request (`JwtAuthFilter`, V2-29), suspended members (V2-23),
  invitations and `pendingInvitations` (V2-30; returned as `[]`).
