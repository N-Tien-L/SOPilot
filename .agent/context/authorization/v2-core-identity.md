# V2 core-api identity and tenancy (V2-11, 2026-11-04)

Read before changing V2 login, access tokens, JIT provisioning or RLS in `services/core-api`.
Source of truth: [TECH-V2-core-api](../../../docs/architecture/components/core-api.md) §3.1–§5.1, ADR-005.
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
- **Roles:** OWNER/ADMIN manage departments, categories and members and read every document and its version
  history; every member lists, reads and downloads readable documents (`download-url`, <= 300 s). OWNER only: audit
  log. **Writing documents is not a role** (V2-36, ADR-009, see "Document publishers" below).
  An ADMIN cannot suspend or remove an OWNER; the workspace always keeps one ACTIVE OWNER (`LAST_OWNER`, checked
  under a row lock on the owners). A PERSONAL workspace cannot be left.
- **Re-issue:** `identity/SessionTokenService.reissue(user, workspace)` re-reads the membership: removed ->
  `401 MEMBERSHIP_LOST`, `SUSPENDED` -> `403 MEMBERSHIP_SUSPENDED`, else a token with current role and `wdept`.
- **Refresh (V2-29, `identity/RefreshTokenService`):** 256-bit token in the `sp_refresh` cookie (HttpOnly,
  SameSite=Strict, path `/api/v1/auth`, 14 days); only its SHA-256 is stored in `core.refresh_tokens` (global, no
  RLS). Each use exchanges it for the next token of the same family under a row lock; a token that was already
  exchanged or revoked revokes the whole family. The membership is re-read on every refresh (removed ->
  `401 MEMBERSHIP_LOST`, suspended -> `403 MEMBERSHIP_SUSPENDED`, chain revoked; suspend/remove/leave through the API already revoke the
  chain, so the next refresh is `401 UNAUTHENTICATED` and the 403 is only a fallback), and the new access token carries
  `wrole`/`wdept` from the database. `/auth/refresh` and `/auth/logout` also require `Origin` =
  `SOPILOT_FRONTEND_ORIGIN`. Suspend, remove and leave revoke the member's chains for that workspace.
- **Workspaces (V2-29):** `workspace/WorkspaceService` (list, current, rename, soft delete) and
  `identity/WorkspaceSessionService` (create TEAM, switch; they issue tokens, so they sit in `identity` to keep
  `ArchitectureTest` cycle-free). `/current` endpoints use the token's `wid`. Delete is soft: `workspaces.deleted_at`,
  one `DOCUMENT_DELETED` outbox event per document; a deleted workspace has no usable membership, so refresh
  ends with `MEMBERSHIP_LOST` (access tokens already issued live <= 15 min). The row is not purged yet.
- `WorkspaceRole` lives in `security` (moved from `WorkspaceRepository`) so `workspace` can use `AuthPrincipal`.
- **Invitations (V2-30, `member/InvitationService`):** OWNER/ADMIN create a link (`POST /invitations`, role `ADMIN` or
  `MEMBER`, never `OWNER`); the 256-bit token is returned once in `inviteUrl` (`<frontend origin>/invite#token=...`),
  stored only as SHA-256, valid 7 days, revocable; no email is sent. One pending invitation per email (an expired one is
  revoked automatically when the same email is invited again). The invitation carries the profile (`displayName`,
  `employeeCode`, `jobTitle`, `departmentId`), applied to the membership on accept; an `ARCHIVED` department or a taken
  `employeeCode` is refused at creation (`409`), and a department archived after the invite is dropped at accept.
- **Accept (`POST /invitations/accept`, `{invitationToken}` xor `{invitationId}`):** the invitee has no workspace yet,
  so redeeming goes through `core.accept_invitation` (SECURITY DEFINER, `V008`) which locks the invitation row
  (`FOR UPDATE`), reads the email from `core.users`, and creates the membership. Same user again (still a member) is
  an idempotent `200`; another user `409 INVITATION_ALREADY_USED`; wrong email `409 INVITATION_EMAIL_MISMATCH` (link
  stays usable); `410 INVITATION_EXPIRED|INVITATION_REVOKED`; by id for another email is `404`. The call then reuses
  `WorkspaceSessionService.switchTo` in the same transaction (token + refresh cookie for the new workspace).
  `pendingInvitations` in the login/refresh payload comes from `core.pending_invitations_for_user`.
- **OWNER rules (V2-30, `member/MemberService`):** `PATCH /members/{id}` accepts `role`. Only an OWNER makes or
  changes an OWNER; ADMIN gets `403`. The acting role is **read from the database** (not `wrole`), so an owner demoted
  since signing in cannot keep acting as one. Demoting, suspending, removing or leaving as the last ACTIVE OWNER is
  `409 LAST_OWNER` (owner rows locked `FOR UPDATE`, so two owners leaving at once leave one). A role change revokes the
  member's refresh chains (`revoked_reason = MEMBERSHIP_LOST`), so the new role reaches the token at the next sign-in.
- **Document publishers (V2-36, ADR-009, `document/DocumentWritePolicy`):** the single place that decides who writes a
  document. Upload, replace, retry, PATCH, `PUT /visibility` and delete need the **publisher of the owning
  department** (`documents.owner_department_id`, visibility `DEPARTMENTS`) or the **workspace publisher** (visibility
  `WORKSPACE`); one publisher each, tables `core.department_publishers` / `core.workspace_publishers`. Everything is read
  from the database inside the write transaction (never `wrole`/`wdept`), and the publisher row is locked `FOR SHARE`,
  so a reassignment applies at the next request without a token refresh and waits for a write in flight. Order of
  answers: not readable -> `404`; readable but not the responsible publisher -> `403 NOT_PUBLISHER`. ADMIN gets `403` on
  every write; an OWNER who is not a publisher too, except **delete** (recall, `actingAs = OWNER`, role read from the
  database) and **`PUT /documents/{id}/ownership`** (OWNER only: moves responsibility between `WORKSPACE` and
  departments or between departments; versions, status and chunks are untouched; sends `ACCESS_UPDATED`). A publisher
  may change `PUT /visibility` only within the same kind and keeping the owner department
  (`409 OWNERSHIP_CHANGE_REQUIRES_OWNER`); the DB also enforces it (`fk_documents_owner_in_scope`, deferred).
  OWNER assigns publishers (`PUT|DELETE /departments/{id}/publisher`, `/publishers/workspace`; `GET /publishers` for
  every member, no email). A member who changes department loses the department-publisher row in the same
  transaction; removing or leaving cascades it (audited as `PUBLISHER_UNASSIGNED`). New workspaces make the creator the
  workspace publisher. `GET /members/me` returns `publisherOf`; document views show `departments`, `ownerDepartment`,
  `fieldSources` and failure details to managers and to the responsible publisher. Payloads to ai-service are unchanged.
- Not yet: workspace domains / `hd` join (FR-05, P1) and CSV invitation import (FR-24, P1): deferred, see TECH §13.
