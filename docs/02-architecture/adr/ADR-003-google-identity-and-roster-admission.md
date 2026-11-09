---
id: ADR-003
title: "Google subject binding and roster admission on every Google login"
status: superseded
created: 2026-10-15
updated: 2026-10-20
author: "Owner"
amends: [ADR-001]
superseded_by: "ADR-005"
---

> **Trạng thái:** Superseded bởi ADR-005 (2026-10-20).

# Google identity and admission

The user approved completing stable Google identity binding and consistent roster admission on 2026-10-15. This decision covers authentication; it does not approve the broader keep/remove product matrix in NEXT-01.

## Decision

- `auth-service` owns `core.external_identities`. Google identity is the canonical issuer `https://accounts.google.com` plus case-sensitive `sub`. Google's legacy issuer spelling `accounts.google.com` is accepted during verification and stored canonically. Email is initial enrollment evidence, not the returning-login key.
- One subject belongs to one local user, and one local user can have one Google identity. Two database uniqueness constraints arbitrate concurrent binding. Existing identities cannot be replaced by a different subject simply because the email matches.
- Every Google login goes through user-service admission. This includes existing accounts and admins. A bound subject checks the roster by claimed local user ID, allowing the Google email to change without switching local accounts. Unbound identities enroll by a verified email and active roster; no backfill by email is run during migration.
- Automatic email enrollment accepts Google-controlled addresses: verified Gmail, or verified Workspace identity with `hd`. A third-party email Google account without `hd` needs a separate account-ownership/linking flow, which is outside M1.
- Pending legacy enrollment must match the account's existing role and department. Mismatch returns 409 for HR review; enrollment does not silently upgrade/downgrade privileges. New accounts receive role/department from the roster. Returning users retain current local account permissions.
- Admin bootstrap and password login remain available. There is no Google admin bypass. General removal of password flows remains a product-scope decision in NEXT-01.
- The admission API is idempotent for a correctly CLAIMED roster. This permits recovery when user-service commits a claim but auth-service fails before completing its own transaction. Google token issuance still requires active/unlocked local account and successful identity binding.
- Legacy gateway authorization-code routes are unregistered. The supported route remains `POST /api/v1/auth/google/verify`; auth-service alone verifies Google and issues SOPilot credentials, as in ADR-002.

## Alternatives and consequences

Email-only login would make renamed/recycled emails ambiguous. Checking only the first login would let an old account bypass the directory. We choose stable identity and a synchronous admission call on every Google login, accepting extra latency and failing closed when user-service is unavailable.

User-service claim and auth-service binding are separate transactions. Admission retries are safe, but this is not a distributed transaction or guaranteed event delivery. Event/outbox work remains NEXT-04. Roster deactivation blocks new Google logins; revocation of already issued sessions still follows local account/session policies and token expiry. Changing all refresh/session policy is outside this decision.

Migration `012_google_identities.sql` is additive and idempotent. Apply it to the intended database before deploying auth-service; the startup validator expects the new table. No production database is migrated by tests.

Provider references: [Google ID token verification, subject and email authority](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).
