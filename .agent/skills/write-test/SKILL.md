---
name: write-test
description: Writing comprehensive unit, integration, and E2E tests across SOPilot's polyglot stack (Spring Boot, FastAPI, NestJS, Next.js).
version: 1.0.0
author: SOPilot Team
---

# Write Test Skill

This skill guides the AI Agent in authoring clean, maintainable, and high-coverage automated tests for all services in the SOPilot monorepo.

---

## When to use this skill
- When implementing any new feature or bug fix.
- When fulfilling ticket `Test Requirements`.
- When adding missing regression tests or increasing test coverage.

---

## 1. Core Testing Standards

### A. The AAA Pattern (Mandatory)
Every test method MUST follow the **Arrange - Act - Assert** pattern with explicit comment headers:
```java
// Arrange: Setup mock data and stub dependencies
// Act: Invoke the target method
// Assert: Verify return value and mock interactions
```

### B. Naming Conventions
- **Java (Spring Boot)**: `<method>_Should<Expected>_When<Condition>()`
  - Example: `claimRoster_ShouldThrowConflictException_WhenAlreadyClaimed()`
- **Python (FastAPI)**: `test_<feature>_<scenario>_<expected>()`
  - Example: `test_rag_pipeline_empty_query_returns_400()`
- **TypeScript (Gateway & Frontend)**: `it('should <expected> when <condition>')`
  - Example: `it('should reject request when JWT token is expired')`

---

## 2. Polyglot Testing Patterns

### A. Spring Boot 3.4 (Java 17)
1. **Service Unit Test (Pure Mockito)**:
   - Annotate with `@ExtendWith(MockitoExtension.class)`.
   - Use `@Mock` for repositories/Feign clients, `@InjectMocks` for the service.
   - Use `when(...).thenReturn(...)` and `verify(mock, times(1)).method(...)`.
   - Never load the full Spring context for pure unit tests (keep execution < 100ms).
2. **Controller Slice Test (`@WebMvcTest`)**:
   - Use `@WebMvcTest(TargetController.class)`.
   - Mock service with `@MockBean`.
   - Perform request using `mockMvc.perform(post("/api/v1/...").contentType(MediaType.APPLICATION_JSON)...)` and assert `andExpect(status().isOk())`.
3. **Repository JPA Slice Test (`@DataJpaTest`)**:
   - Verify unique constraints, custom JPQL queries, and cascade behaviors.

### B. Python 3.12+ (FastAPI)
1. **Async Unit & Route Testing**:
   - Use `pytest-asyncio` with `@pytest.mark.asyncio`.
   - Use `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.
   - Mock external calls (Groq API, Jina AI, RabbitMQ) using `unittest.mock.AsyncMock` or `respx`.
2. **Deterministic Fixtures**:
   - Place shared fixtures in `conftest.py`.

### C. NestJS 11 (API Gateway)
1. **Guard & Route Testing**:
   - Use `Test.createTestingModule(...)`.
   - Override guards when testing routing: `.overrideGuard(JwtAuthGuard).useValue({ canActivate: () => true })`.
   - Test RBAC: Verify that requests without `ADMIN` role are rejected with `403 Forbidden`.

### D. Next.js 16 (Frontend Web)
1. **Component & Hook Testing**:
   - Use `@testing-library/react` and `userEvent`.
   - Mock Zustand store state (`useAuthStore.setState({ user: mockUser })`).
   - Mock Axios API client methods (`vi.spyOn(api, 'post').mockResolvedValue(...)`).

---

## 3. Mandatory Test Coverage Checklist
For every implemented endpoint or service method, you MUST cover:
- [ ] **Happy Path**: Valid inputs return 200/201 with expected payload.
- [ ] **Validation Failure**: Missing or invalid fields return 400 with structured error response.
- [ ] **Duplicate / Conflict**: Violating unique index (e.g. duplicate email) returns 409 Conflict.
- [ ] **Not Found**: Non-existent UUID returns 404 Not Found.
- [ ] **Unauthorized / Forbidden**: Invalid token returns 401; insufficient role returns 403.
- [ ] **Edge Cases**: Empty list, null strings, boundary numbers.

---

## 4. File Placement
- Spring Boot: `services/<service-name>/src/test/java/com/poliwise/<service>/...`
- FastAPI: `services/ai-qa-service/tests/unit/` and `tests/integration/`; `services/ingestion-service/tests/ingestion_tests/` (no unit/integration split, run with `-Type all`)
- API Gateway: `services/api-gateway/src/**/*.spec.ts`
- Frontend: no test runner is configured yet (`frontend/web/package.json` has no `test` script). Until one is added, the frontend gates are `pnpm build` and `pnpm lint`.

---

## 5. Running and Pre-Commit Verification
Running suites is covered by the `run-test` skill. Before proposing a commit, run `./scripts/pre-commit-check.ps1`; it checks the diff for debug statements, secrets, `.env` files and TODO/FIXME without a ticket reference, then runs tests for the affected services.

---

## 6. References
- Testing strategy: `references/testing-strategy.md`
- Mock patterns: `references/mock-patterns.md`
- Stack patterns: `resources/test-patterns-java.md`, `resources/test-patterns-python.md`, `resources/test-patterns-nestjs.md`, `resources/test-patterns-nextjs.md`
