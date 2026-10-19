# Google admission — 2026-10-15

Read when changing Google login, linking provider identities, or claiming employee roster entries.

- Policy and trade-offs: `docs/02-architecture/adr/ADR-003-google-identity-and-roster-admission.md`.
- Exact DTO/status/ownership contract: `docs/02-architecture/designs/TECH-google-admission.md`.
- auth-service owns `core.external_identities`; user-service owns roster admission. Apply additive migration 012 before deploying auth-service.
- Resolve a returning Google account by canonical issuer plus subject. Use email only to enroll an unbound, authoritative Google identity against an eligible roster.
- Every Google login requires roster admission, including admins. Password/bootstrap access remains available. Match legacy account role and department before first enrollment; mismatch requires HR review.
- Expected refresh-token expiration/replay rejection commits its revocation through `RefreshTokenRejectedException` at both transactional service boundaries. Other failures retain normal rollback behavior.
- Roster removal blocks new Google login. Existing access/refresh sessions follow account/session revocation policy; roster removal alone is not an immediate global session revocation operation.
- Test with `scripts/test-google-auth.ps1`: real backend HTTP, fresh test PostgreSQL, locally signed tokens/JWKS. It does not certify Google's hosted browser flow or the rest of M1-06.
