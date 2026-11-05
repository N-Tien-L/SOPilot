# core-api (V2)

Spring Boot 3.5, Java 21. Owns schema `core` and is the only writer of `core.users`
([TECH-V2-core-api](../../docs/02-architecture/designs/TECH-V2-core-api.md), ADR-004/005).
Package: `com.sopilot.core` (modules `common`, `config`, `security`, `tenancy`, `identity`, `workspace`).

Implemented so far (V2-11): Google login with nonce, JIT user + PERSONAL workspace + OWNER
membership, RS256 access token (≤ 15 min, claims `wid`/`wrole`/`wdept`), JWKS, dev login for
`local`/`test`. Refresh/switch/logout are V2-29; departments and `wdept` values V2-23;
invitations V2-30.

## Endpoints

| Method & path | Access | Notes |
|---|---|---|
| `POST /api/v1/auth/google/nonce` | Public | `{data:{nonce}}` + HttpOnly cookie `sp_nonce` (5 min, HMAC-signed) |
| `POST /api/v1/auth/google` | Public | `{idToken}` + cookie `sp_nonce`; `401 INVALID_GOOGLE_TOKEN` on any failure |
| `POST /api/v1/auth/dev-login` | Public, **`local`/`test` profile only** | `{email, displayName?}`; issuer `sopilot-dev`; `404` in any other profile |
| `GET /.well-known/jwks.json` | Public | Public signing key for ai-service |
| `GET /actuator/health` | Public | No details |

## Configuration

No profile is active by default. Outside `local`/`test` the service refuses to start without
`SOPILOT_JWT_PRIVATE_KEY_PATH` and `SOPILOT_NONCE_HMAC_KEY`, and dev login does not exist.

| Env | Default | Notes |
|---|---|---|
| `SPRING_PROFILES_ACTIVE` | none | `local` for development, `test` for automated tests/eval |
| `SOPILOT_DB_URL`, `SOPILOT_DB_USER`, `SOPILOT_DB_PASSWORD` | `jdbc:postgresql://localhost:55432/sopilot`, `sopilot_core_app`, — | Use the `sopilot_core_app` role from `docker-compose.v2.yml` |
| `GOOGLE_CLIENT_ID` | — | Blank rejects every Google login |
| `SOPILOT_JWT_PRIVATE_KEY_PATH`, `SOPILOT_JWT_KID` | in-memory key in `local`/`test` | Unencrypted PKCS#8 PEM, RSA ≥ 2048; kid defaults to the key thumbprint |
| `SOPILOT_ACCESS_TTL` | `PT15M` | Startup fails above 15 minutes |
| `SOPILOT_NONCE_HMAC_KEY` | random in `local`/`test` | ≥ 32 bytes |

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
