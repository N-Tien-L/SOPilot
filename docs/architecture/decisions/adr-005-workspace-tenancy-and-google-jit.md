---
id: ADR-005
title: "V2: the workspace is the tenant; Google JIT sign-in, invitations and domain join replace the roster"
status: approved
created: 2026-10-16
updated: 2026-11-13
author: "Owner"
refs: [docs/product/prd-v2-sopilot-mvp.md, docs/architecture/decisions/adr-004-two-service-architecture.md]
deciders: ["Owner"]
amends: []
supersedes: [ADR-001, ADR-003]
superseded_by: ""
---

# ADR-005: The workspace is the tenant; Google JIT, invitations and domains replace the roster

> **Status:** `approved` (2026-10-20) | **Proposed:** `2026-10-16` | **Decider:** `Owner`
>
> On approval this ADR replaced ADR-001 (roster owned by user-service) and ADR-003 (roster admission on every Google login). ADR-003's identity binding rule on `(issuer, sub)` is kept unchanged.
>
> Translated from Vietnamese on 2026-11-13; section numbers are stable (cited by code).

---

## 1. Context and the decision to make
- Code review on 2026-10-16: there is no notion of an organization in the schema, the JWT or the specs. `core.employee_roster` has a globally unique email; departments and access rules are global; `ai-qa-service` (`chunk_repo.py`) filters chunks by role/department/user, not by organization.
- Every Google sign-in needs a roster entry, so individual users and teams without HR are blocked.
- PRD-V2 needs one model that serves individuals, startups and companies, with absolute data isolation.

## 2. Evaluation criteria
1. No data leaks between tenants, even when one query has a programming error.
2. Onboarding without an administrator for individual users.
3. Companies still control who enters a workspace.
4. ai-service does not have to call core-api on every request to check access.

## 3. Options considered

### Tenant model
- **A. Keep the roster, add `organization_id` to every table.** (−) Still needs HR for every user; no way in for a solo user.
- **B. Workspace + membership (chosen).** Users are global; the workspace is the tenant; the membership carries the role. One person can belong to many workspaces. A solo user is a special case: a one-member workspace.
- **C. A separate database/schema per tenant.** (−) Too heavy for the free tier and for eval.

### Data isolation
- **Application-layer filtering only.** (−) One query that forgets `WHERE workspace_id` is a leak.
- **Application filtering + Postgres RLS (chosen).** Tables with `workspace_id` enable RLS with the policy `workspace_id = current_setting('app.workspace_id')::uuid`. Each transaction sets `SET LOCAL app.workspace_id` from the token. The application's database role does not own the tables and has no `BYPASSRLS`.

### Token scope
- **Per-user token, membership checked on every request.** (−) ai-service would have to call core-api or read schema `core`.
- **Per-workspace token (chosen).** The access token carries `sub` (user id), `wid` (the active workspace) and `wrole`. Switching workspace calls `POST /api/v1/auth/switch-workspace` to get a new token.

## 4. Decision and rationale
- **Chosen:** workspace + membership; application filtering + RLS; per-workspace access tokens.

### 4.1 Google sign-in (JIT)
1. Verify the ID token as before (`GoogleTokenVerifierService`): RS256/JWKS, `iss`, `aud`, `exp`, `email_verified`. Add a `nonce` check. Return no internal error details to the client.
2. Find the user by `(issuer, sub)` in `core.external_identities`. If absent, create the user + identity in one transaction (JIT). Never link by email.
3. A new user gets a personal workspace with role `OWNER` (idempotent).
4. Apply pending invitations or domain join (4.2), then issue a token for the most recently active workspace.
5. Google accounts have no password; the password-hash column is dropped.

### 4.2 Joining a workspace
- **Invitations:** `core.invitations(workspace_id, email, role, token_hash, expires_at, accepted_at, revoked_at)`. Only the token's hash is stored. Accepted only when Google's verified email matches the invited email (case-insensitive comparison). Each invitation can be used once.
- **Domain (P1):** `core.workspace_domains(workspace_id, domain)`. Only an owner whose `hd` claim equals that exact domain can register it, so no DNS verification is needed. People who sign in with a matching `hd` see the workspace and join with role `MEMBER`. Personal Gmail addresses never match a domain.

### 4.3 Roles and rules
| Action | OWNER | ADMIN | MEMBER |
|---|---|---|---|
| Ask, view/download documents, give feedback | ✓ | ✓ | ✓ |
| Upload/delete documents, view knowledge gaps | ✓ | ✓ | |
| Invite, remove members, change roles (never touching an OWNER) | ✓ | ✓ | |
| Promote/demote an OWNER, enable domains, delete the workspace, view audit | ✓ | | |

> **Changed 2026-11-10 by [ADR-009](adr-009-department-publishers.md):** writing documents is no longer a role. Uploads and deletes belong to the publisher of the document's scope, the OWNER can revoke any document, and an ADMIN does not write documents. The "Upload/delete documents" row above is historical.

A workspace always keeps at least one `OWNER`. A personal workspace cannot be deleted while it is the user's only workspace.

### 4.4 Revoking access
- Access tokens live ≤ 15 minutes. On refresh, core-api re-checks the membership for `wid`; without a membership it no longer issues tokens for that workspace.
- So removing a member takes effect at the latest after one access-token lifetime. This delay is accepted for the MVP and documented in the security documentation.

### 4.5 Isolation in ai-service
- `rag.chunks`, `rag.conversations`, `rag.messages` and `rag.ingestion_jobs` all have `workspace_id` and enable RLS.
- Every retrieval query has `workspace_id = :wid` taken from the verified token, never from the request body.
- The FR-19 test suite proves isolation at both the HTTP and SQL levels.

## 5. Impact and consequences
- **Positive:** one model serves solo users, startups and companies; isolation has two layers; ai-service does not depend on core-api when serving a request.
- **Trade-offs:**
  - ~~Departments and department-based permissions are lost in V2.~~ Proposed 2026-10-19: [ADR-007](adr-007-departments-member-profiles-document-access.md) keeps flat departments inside the workspace and department-based read access to documents.
  - Revocation latency ≤ the access-token lifetime.
  - RLS needs disciplined connection handling (`SET LOCAL` in every transaction); tests must show that `app.workspace_id` does not leak through the connection pool.
- **Next actions (historical, done):**
  - DDL for `core` (users, external_identities, workspaces, memberships, invitations, workspace_domains, refresh_tokens, documents, feedback, audit_logs) and `rag` in the TECH design.
  - On approval: set ADR-001 and ADR-003 to `superseded`; rewrite the authorization context docs for the workspace model (now `docs/architecture/domain/identity-and-access.md`).
