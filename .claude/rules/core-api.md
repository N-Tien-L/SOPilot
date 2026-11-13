---
paths:
  - "services/core-api/**"
---

# core-api (Spring Boot 3.5, Java 21, Maven)

Design source: `docs/architecture/components/core-api.md`. Endpoint table and env vars: `services/core-api/README.md`. Roles, tokens, publishers: `docs/architecture/domain/identity-and-access.md`.

## Structure

- Package by feature under `com.sopilot.core.<module>` (`audit`, `department`, `document`, `identity`, `member`, `outbox`, `storage`, `workspace`, plus shared `common`, `config`, `security`, `tenancy`). Put new code in the feature package, not in layer packages.
- `XController` → `XService` → `XRepository`. Repositories use `JdbcTemplate` with hand-written SQL and nested `record` row types. There is no JPA/Hibernate and no MapStruct; do not add them.
- Request/response DTOs are `record`s nested in the controller (`CreateRequest`, `DepartmentView.of(...)`). Wrap responses in `ApiResponse.of(...)`; paging uses `PageResponse` + `Cursor`.
- IDs: `UuidV7.generate()`.
- Enforced by `ArchitectureTest` (in `./mvnw test`): controllers never touch repositories or JDBC; JDBC only in `*Repository` (listed baseline exceptions); `RlsContext` used only by `TenantTx`/`IdentityService`; `common` independent of features; no module cycles; no `System.out`. If it fails, move the code behind a service. Do not add exceptions without the owner agreeing.

## Tenancy and authorization (FR-19, highest risk)

- Every read/write of a table with `workspace_id` runs inside `tenant.run(principal, () -> ...)` (`TenantTx`). It binds `app.workspace_id`/`app.user_id` with `set_config(..., true)` for that transaction only.
- The tenant comes from the verified `AuthPrincipal` (token `wid`/`wrole`/`wdept`), or for internal callbacks from the event being processed. Never take a workspace id from the path, body or query.
- Also filter by `workspace_id` in SQL. RLS is the second layer, not the only one. Another workspace's id must produce `404`, not `403`.
- Role checks sit at the start of the service method: `principal.requireManager()` / `requireOwner()`.
- Cross-workspace reads go only through reviewed `SECURITY DEFINER` functions in a migration (for example `core.create_personal_workspace`, `core.referenced_object_keys`).
- Proof: `TenantIsolationIT`, `TenantIsolationApiIT` (CI workflow `tenant-isolation.yml`). Any new tenant table or endpoint needs a case there.

## Errors, logging, side effects

- Business errors: `throw new ApiException(HttpStatus.X, "STABLE_CODE", "Fixed client-safe message.")`. Never build a message from `e.getMessage()` (A8). `GlobalExceptionHandler` renders `{"error":{code,message,details},"traceId"}`.
- Never log ID tokens, access tokens, the nonce cookie, keys or `X-Internal-Token`. Google rejections log only a reason code.
- State change + audit + outbox in the same `tenant.run`: `audit.record(principal, "ACTION", "TYPE", id, details)` and `OutboxService.enqueue(...)`. Calls to ai-service happen only from `OutboxDispatcher` after commit. S3 deletes use `AfterCommit.run(...)`.
- `/internal/**` is authenticated by `InternalTokenFilter` (`X-Internal-Token`). Every other `/api/v1/**` route except `/api/v1/auth/**` requires the bearer token.

## Tests

- Unit tests: `*Test`, no Spring context and no Docker. Integration tests: `*IT`. They need Docker (Testcontainers pgvector + real Flyway chains + production roles). API-level tests extend `support/ApiIT`; DB-level tests call `V2Postgres.register(registry)`.
- Use the in-process fakes `support/InMemoryStorage` and `support/RecordingAiClient` (wired in `TestBeans`) rather than Mockito. Mockito appears in only one test.
- Test names are behaviour sentences in camelCase (`fourConcurrentUploadsOfTheSameBytesCreateOneDocument`). No `should_When` pattern and no AAA comment headers.
- Commands: `./scripts/run-tests.ps1 -Scope core-api -Type unit` (fast; includes ArchitectureTest), `-Type all` (= `mvnw verify`, Docker). Single test: `cd services/core-api; ./mvnw test -Dtest=ClassName#method`, or `./mvnw verify -Dit.test=ClassNameIT -Dtest=NoSuchTest -Dsurefire.failIfNoSpecifiedTests=false`.
