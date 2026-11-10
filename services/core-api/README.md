# core-api (V2)

Spring Boot 3.5, Java 21. Owns schema `core` and is the only writer of `core.users`
([TECH-V2-core-api](../../docs/02-architecture/designs/TECH-V2-core-api.md), ADR-004/005).
Package: `com.sopilot.core` (modules `common`, `config`, `security`, `tenancy`, `identity`, `workspace`, `member`,
`department`, `document`, `outbox`, `storage`, `audit`).

Implemented so far (V2-11): Google login with nonce, JIT user + PERSONAL workspace + OWNER
membership, RS256 access token (≤ 15 min, claims `wid`/`wrole`/`wdept`), JWKS, dev login for
`local`/`test`. Invitations are V2-30.

Added by V2-29: rotating refresh tokens (`sp_refresh` cookie, replay detection, membership re-read on every refresh),
logout, workspace switch, workspace CRUD (create TEAM, list, current, rename, soft delete), refresh revoked on
suspend/remove/leave, and JWKS that also publishes the previous signing key during a rotation.

Added by V2-23: flat departments, member profiles, suspend/reactivate/remove/leave with the last-owner and
admin-vs-owner rules, `wdept` from the database at token re-issue (`SessionTokenService`).
Added by V2-12: documents (PDF with a text layer, Markdown), versions, quota, outbox to ai-service, status callbacks,
S3 storage and orphan janitor, audit log. Every `/api/v1/**` route except `/api/v1/auth/**` needs a bearer token
(`JwtAuthFilter`); `/internal/**` needs `X-Internal-Token`.

## Endpoints

| Method & path | Access | Notes |
|---|---|---|
| `POST /api/v1/auth/google/nonce` | Public | `{data:{nonce}}` + HttpOnly cookie `sp_nonce` (5 min, HMAC-signed) |
| `POST /api/v1/auth/google` | Public | `{idToken}` + cookie `sp_nonce`; `401 INVALID_GOOGLE_TOKEN` on any failure |
| `POST /api/v1/auth/dev-login` | Public, **`local`/`test` profile only** | `{email, displayName?}`; issuer `sopilot-dev`; `404` in any other profile |
| `POST /api/v1/auth/refresh` | Cookie `sp_refresh` + `Origin` = `SOPILOT_FRONTEND_ORIGIN` | Rotates the cookie, returns the same body as login; replay revokes the chain; `401 UNAUTHENTICATED\|MEMBERSHIP_LOST`, `403 MEMBERSHIP_SUSPENDED`; a rejection also clears the cookie |
| `POST /api/v1/auth/logout` | Cookie + `Origin` | Always `204`; revokes the chain and clears the cookie |
| `POST /api/v1/auth/switch-workspace` | Bearer | `{workspaceId}`; `404` if not a member (or deleted), `403 MEMBERSHIP_SUSPENDED`; ends the old chain, starts a new one |
| `GET /api/v1/workspaces`, `GET\|PATCH\|DELETE /api/v1/workspaces/current` | Member; PATCH/DELETE OWNER | `/current` is the token's workspace, no id in the path; PERSONAL cannot be deleted (`409 PERSONAL_WORKSPACE`) |
| `POST /api/v1/workspaces` | Bearer | `{name}` creates a TEAM workspace with the caller as OWNER; `201` with tokens for it |
| `GET /.well-known/jwks.json` | Public | Current and, during a rotation, previous public signing key for ai-service |
| `GET /actuator/health` | Public | No details |
| `GET/POST /api/v1/departments`, `PATCH/DELETE /api/v1/departments/{id}` | Member read; OWNER/ADMIN write | `409 DEPARTMENT_NAME_TAKEN`, `409 DEPARTMENT_IN_USE` (counts) |
| `GET /api/v1/members`, `PATCH /members/{userId}`, `POST /members/{userId}/suspend\|reactivate`, `DELETE /members/{userId}` | OWNER/ADMIN | ADMIN cannot touch an OWNER; `409 LAST_OWNER` |
| `GET /api/v1/members/me`, `POST /api/v1/members/leave` | Member | A PERSONAL workspace cannot be left |
| `GET/POST /api/v1/categories`, `PATCH/DELETE /api/v1/categories/{id}` | Member read; OWNER/ADMIN write | `409 CATEGORY_NAME_TAKEN`; deleting sets document category to null without altering access |
| `GET /api/v1/tags` | Member | List tags in current workspace |
| `POST /api/v1/documents`, `POST /documents/{id}/versions`, `POST /documents/{id}/retry`, `PATCH`, `DELETE /documents/{id}` | OWNER/ADMIN | PDF/MD <= 20 MB; `415`, `413`, `409 DUPLICATE_DOCUMENT\|QUOTA_EXCEEDED\|VERSION_IN_PROGRESS\|DOCUMENT_UNCHANGED\|VERSION_NOT_FAILED`; upload takes `file` plus optional `visibility=DEPARTMENTS`, `departmentIds` (duplicates ignored), `title` (1-200 chars, becomes a `USER` title), `categoryId`, `tags`; PATCH updates metadata + `categoryId`, `tags` (sets field sources to `USER`) |
| `PUT /api/v1/documents/{id}/visibility` | OWNER/ADMIN | `{visibility, departmentIds[]}`; bumps `access_revision`, writes `ACCESS_UPDATED`, after commit it is sent to ai-service on the request thread with a 2 s timeout: `APPLIED` when delivered, `PENDING` when the dispatcher will retry; returns `{accessSync: APPLIED\|PENDING}` |
| `GET /api/v1/documents`, `GET /documents/{id}`, `GET /documents/{id}/download-url` | Member (read scope) | Cursor paging, filters `categoryId`, `tag`; another workspace's id or unpermitted department doc is `404`; members see masked `departments`/`fieldSources` |
| `GET /api/v1/documents/{id}/versions` | OWNER/ADMIN | History and failure reasons |
| `GET /api/v1/audit-logs` | OWNER | Filters `action`, `actorId`, `from`, `to`, `cursor` |
| `PATCH /internal/documents/{id}/versions/{versionId}/status` | `X-Internal-Token` | ai-service callback; stale `attempt` is ignored with `200 {applied:false}` |

## Configuration

No profile is active by default. Outside `local`/`test` the service refuses to start without
`SOPILOT_JWT_PRIVATE_KEY_PATH` and `SOPILOT_NONCE_HMAC_KEY`, and dev login does not exist.

Copy `.env.example` in this directory to `.env`; it lists the variables below with local values and the PowerShell line that loads them into the shell (Spring does not read `.env` itself).

| Env | Default | Notes |
|---|---|---|
| `SPRING_PROFILES_ACTIVE` | none | `local` for development, `test` for automated tests/eval |
| `SOPILOT_DB_URL`, `SOPILOT_DB_USER`, `SOPILOT_DB_PASSWORD` | `jdbc:postgresql://localhost:55432/sopilot`, `sopilot_core_app`, — | Use the `sopilot_core_app` role from `docker-compose.v2.yml` |
| `GOOGLE_CLIENT_ID` | — | Blank rejects every Google login |
| `SOPILOT_JWT_PRIVATE_KEY_PATH`, `SOPILOT_JWT_KID` | in-memory key in `local`/`test` | Unencrypted PKCS#8 PEM, RSA ≥ 2048; kid defaults to the key thumbprint |
| `SOPILOT_ACCESS_TTL` | `PT15M` | Startup fails above 15 minutes |
| `SOPILOT_REFRESH_TTL` | `P14D` | Refresh-token lifetime |
| `SOPILOT_FRONTEND_ORIGIN` | `http://localhost:3000` | The only `Origin` accepted by refresh and logout |
| `SOPILOT_JWT_PREVIOUS_PUBLIC_KEY_PATH` | unset | X.509 PEM public key of the key being replaced; keep it for one access-token lifetime after rotating (`openssl pkey -in old.pem -pubout`) |
| `SOPILOT_NONCE_HMAC_KEY` | random in `local`/`test` | ≥ 32 bytes |
| `SOPILOT_INTERNAL_TOKEN`, `SOPILOT_AI_BASE_URL` | blank (rejects every `/internal` call), `http://ai-service:8000` | One token shared with ai-service |
| `SOPILOT_S3_ENDPOINT`, `SOPILOT_S3_BUCKET`, `SOPILOT_S3_ACCESS_KEY`, `SOPILOT_S3_SECRET_KEY`, `SOPILOT_S3_REGION` | blank, blank, blank, blank, `us-east-1` | Unset storage fails document operations with `503`, not startup |
| `SOPILOT_QUOTA_DOCS_PER_WORKSPACE`, `SOPILOT_QUOTA_BYTES_PER_WORKSPACE` | `50`, `209715200` | `0` turns a limit off |
| `SOPILOT_OUTBOX_POLL`, `SOPILOT_OUTBOX_MAX_ATTEMPTS` | `PT5S`, `20` | Backoff `2^attempts` s, cap 10 min, jitter |

Generate a signing key (keep it outside the repo; `*.pem` is ignored here):

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out core-api-jwt.pem
```

## Commands

Run from the repository root unless noted.

```powershell
./scripts/validate-build.ps1 -Scope core                  # mvnw compile
./scripts/run-tests.ps1 -Scope core-api -Type unit        # unit tests (no Docker)
./scripts/run-tests.ps1 -Scope core-api -Type all         # + *IT integration tests (Docker required)

cd services/core-api
./mvnw test                                               # unit tests
./mvnw verify                                             # unit + Testcontainers integration tests
./mvnw spring-boot:run "-Dspring-boot.run.profiles=local" # needs the V2 Postgres from docker-compose.v2.yml
```

Integration tests (`*IT`) cover departments/members, the document lifecycle, concurrent quota and duplicate
uploads, the outbox, MinIO (`minio/minio:RELEASE.2024-05-10T01-41-38Z`, the tag `docker-compose.v2.yml` pins) and
tenant isolation through the API (`TenantIsolationApiIT`). S3 and ai-service are in-process fakes except in
`S3StorageClientIT` and `HttpAiServiceClientTest`.

Integration tests start a disposable `pgvector/pgvector:0.8.0-pg16` container, run the real
`infrastructure/db/init/01-roles.sh`, apply both Flyway chains as `sopilot_migrator` and connect
as `sopilot_core_app` with random passwords. They never touch the `sopilot-v2` volumes.

## Rules

- Errors use `{"error": {"code", "message", "details"}, "traceId"}`; messages are fixed text,
  never `e.getMessage()` (A8). Google rejections log only a reason code.
- Never log ID tokens, access tokens, nonce cookies or keys.
- RLS variables are set per transaction (`RlsContext`, `set_config(..., true)`), from verified
  identity only. Cross-workspace operations go through reviewed `SECURITY DEFINER` functions.
- Schema changes are new files in `infrastructure/db/migrations/core/`; the app role never runs Flyway.
